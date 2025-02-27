from typing import Any, Generator
import clickhouse_connect
import pytest
from clickhouse_connect.driver import Client
from django.conf import settings


pytest_plugins = (
    'celery.contrib.pytest',
)


@pytest.fixture(scope='session')
def f_ch_client() -> Generator[Client] :

    ch_default_schema = settings.CLICKHOUSE_SCHEMA
    ch_test_schema = settings.CLICKHOUSE_TEST_SCHEMA_NAME
    ch_table_name = settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME

    ch_client_kwargs = {
        'host': settings.CLICKHOUSE_HOST,
        'port': settings.CLICKHOUSE_PORT,
        'user': settings.CLICKHOUSE_USER,
        'password': settings.CLICKHOUSE_PASSWORD,
    }

    client = clickhouse_connect.get_client(**ch_client_kwargs)

    client.command(
        f'CREATE DATABASE IF NOT EXISTS {ch_test_schema}'
    )

    client.set_client_setting('database', ch_test_schema)

    client.command(
        f'CREATE TABLE IF NOT EXISTS {ch_table_name} '
        f'AS {ch_default_schema}.{ch_table_name}'
    )
    
    yield client

    client.command(
        f'TRUNCATE TABLE IF EXISTS {ch_test_schema}.{ch_table_name}'
    )
    
    client.close()
