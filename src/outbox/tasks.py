from celery import Task, shared_task
from outbox.services import ClickHouseOutboxService
import structlog
from core.consts import DATABASE_CONNECTION_ERRORS

logger = structlog.get_logger(__name__)


@shared_task(
    bind=True,
    name='outbox.tasks.migrate_outbox_to_olap_database',
    autoretry_for=DATABASE_CONNECTION_ERRORS,
    max_retries=5,
    retry_backoff=60,
    retry_jitter=False,
)
def migrate_outbox_to_clickhouse(self: Task):
    ClickHouseOutboxService().migrate_events()
