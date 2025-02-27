from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from clickhouse_connect import get_client
from clickhouse_connect.driver.exceptions import ClickHouseError
from clickhouse_connect.driver.client import Client

from django.conf import settings

import structlog

from outbox.consts import CH_EVENT_LOG_COLUMNS

logger = structlog.get_logger(__name__)


class EventLogClient(ABC):
    @abstractmethod
    def insert(self, data):
        """It inserts a batch of events into an olap database."""
        pass
    
    @abstractmethod
    def query(self, query):
        """It sends queries to an olap database."""
        pass


class ClickHouseEventLogClient(EventLogClient):
    def __init__(self, client: Client) -> None:
        self._client = client

    @classmethod
    @contextmanager
    def init(cls) -> Generator['ClickHouseEventLogClient']:
        client = get_client(
            host=settings.CLICKHOUSE_HOST,
            port=settings.CLICKHOUSE_PORT,
            user=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
            query_retries=2,
            connect_timeout=30,
            send_receive_timeout=10,
        )
        try:
            yield cls(client)
        except Exception as e:
            logger.error('error while executing clickhouse query', error=str(e))
        finally:
            client.close()

    def insert(
        self,
        data: list[tuple],
    ) -> int:
        
        try:
            return self._client.insert(
                data=data,
                column_names=CH_EVENT_LOG_COLUMNS,
                database=settings.CLICKHOUSE_SCHEMA,
                table=settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME,
            ).written_rows
        except ClickHouseError as e:
            logger.error('Unable to insert data to clickhouse', error=str(e))
            raise e

    def query(self, query: str) -> Any:  # noqa: ANN401
        logger.debug('executing clickhouse query', query=query)

        try:
            return self._client.query(query).result_rows
        except ClickHouseError as e:
            logger.error('Failed to execute clickhouse query', error=str(e))
            return
