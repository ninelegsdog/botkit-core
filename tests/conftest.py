"""Shared test fixtures for botkit-core integration tests."""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """Create event loop for session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    """PostgreSQL 16 container for integration tests."""
    container = PostgresContainer("postgres:16-alpine")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def redis_container() -> RedisContainer:
    """Redis 7 container for integration tests."""
    container = RedisContainer("redis:7-alpine")
    container.start()
    yield container
    container.stop()


@pytest.fixture
def postgres_url(postgres_container: PostgresContainer) -> str:
    """Get PostgreSQL connection URL."""
    return postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest.fixture
def redis_url(redis_container: RedisContainer) -> str:
    """Get Redis connection URL."""
    return f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}"


@pytest.fixture
async def db_engine(postgres_url: str):
    """Create async SQLAlchemy engine."""
    engine = create_async_engine(postgres_url, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests."""
    async_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def redis_client(redis_url: str):
    """Create Redis client for tests."""
    import redis.asyncio as redis
    client = redis.from_url(redis_url, decode_responses=True)
    yield client
    await client.aclose()


# Markers for test classification
def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests as integration tests requiring containers")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "serial: marks tests that cannot run in parallel")


# Skip integration tests if testcontainers not available
def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-integration", default=False):
        skip_integration = pytest.mark.skip(reason="need --run-integration option to run")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests with testcontainers",
    )
