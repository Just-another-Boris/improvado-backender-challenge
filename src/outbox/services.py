from abc import ABC, abstractmethod
from typing import Type
from outbox.models import EventLogOutbox
from core.base_model import Model 
import re
from django.conf import settings
from django.db import transaction, DatabaseError, InterfaceError
from django.utils import timezone
import structlog
from outbox.clients import EventLogClient
from django.db.models.query import QuerySet
from outbox.consts import CH_EVENT_LOG_COLUMNS
from sentry_sdk import capture_exception
from core.utils import get_class_by_full_path

logger = structlog.get_logger(__name__)


class BaseOutboxService(ABC):
    @abstractmethod
    def save_events(self):
        """It saves events into an outbox table."""
        pass

    @abstractmethod
    def migrate_events(self):
        """It migrates(moves) events form an outbox table into an olap database 
        using an event log client."""
        pass


class ClickHouseOutboxService(BaseOutboxService):
    def __init__(
        self,
        event_log_client: Type[EventLogClient] | None = None,
        migration_min_batch_size: int | None = None,
        migration_queryset_fields: list | None = None,
    ) -> None:
        self.event_log_client = (
            event_log_client or get_class_by_full_path(settings.OUTBOX_DEFAULT_EVENT_LOG_CLIENT_CLASS)
        )
        self.migration_min_batch_size = (
            migration_min_batch_size or settings.OUTBOX_MIGRATION_MIN_BATCH_SIZE
        )
        self.migration_queryset_fields = (
            migration_queryset_fields or CH_EVENT_LOG_COLUMNS
        )

    def save_events(
        self, events: Model | list[Model],
    ) -> list[EventLogOutbox]:
        events = events if isinstance(events, (list, tuple,)) else [events]
        prepared_data = self._prepare_data(events)
        
        try:
            with transaction.atomic():
                saved_events = EventLogOutbox.objects.bulk_create(objs=prepared_data)
        except (DatabaseError, InterfaceError,) as e:
            logger.error('failed to save events to outbox', error=str(e))
            capture_exception(e)
            raise e
        
        return saved_events

    def migrate_events(self) -> int:
        logger.info('event outbox migration started')
        
        migration_queryset = (
            self._get_migration_queryset()
            .select_for_update(skip_locked=True)
        )
        
        try:
            with transaction.atomic():
                migration_batch = list(migration_queryset)

                if not len(migration_batch) >= self.migration_min_batch_size:
                    return

                migration_queryset.update(is_processed=True)
                
                with self.event_log_client.init() as client:
                    rows_migrated = client.insert(migration_batch)
        except Exception as e:
            logger.error('outbox migration failed', error=str(e))
            capture_exception(e)
            raise e
        
        logger.info('event outbox migration finished')

        return rows_migrated

    def _prepare_data(self, data: list[Model]) -> list[EventLogOutbox]:
        return [
            EventLogOutbox(
                event_type=self._to_snake_case(event.__class__.__name__),
                event_date_time=timezone.now(),
                environment=settings.ENVIRONMENT,
                event_context=event.model_dump_json(),
            )
            for event in data
        ]
    
    def _to_snake_case(self, event_name: str) -> str:
        result = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', event_name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', result).lower()

    def _get_migration_queryset(self) -> QuerySet:        
        return (
            EventLogOutbox.unprocessed_objects
            .values_list(*self.migration_queryset_fields)
        )
