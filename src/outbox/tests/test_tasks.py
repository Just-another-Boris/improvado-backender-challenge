import pytest
from outbox.models import EventLogOutbox
from outbox.tasks import migrate_outbox_to_clickhouse
from clickhouse_connect.driver import Client
from django.conf import settings


# pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
        'f_populate_outbox',
        [3],
        indirect=True,
)
@pytest.mark.django_db(transaction=True)
def test_outbox_migrated_after_task_run(
    celery_worker, 
    f_populate_outbox, 
    f_ch_client: Client,
    settings,
):
    settings.CLICKHOUSE_SCHEMA = settings.CLICKHOUSE_TEST_SCHEMA_NAME
    settings.OUTBOX_MIGRATION_MIN_BATCH_SIZE = 3
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPOGATES = True

    ch_count_select = f'SELECT count(*) FROM {settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}'
    unprocessed_count_before = EventLogOutbox.unprocessed_objects.count()
    
    assert f_ch_client.command(ch_count_select) == 0
    
    migrate_outbox_to_clickhouse.apply()

    assert EventLogOutbox.objects.filter(is_processed=True).count() == unprocessed_count_before
    assert f_ch_client.command(ch_count_select) == unprocessed_count_before

