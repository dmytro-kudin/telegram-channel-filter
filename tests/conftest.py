import pytest

from channel_filter import db


@pytest.fixture
async def conn():
    connection = await db.connect(":memory:")
    yield connection
    await connection.close()
