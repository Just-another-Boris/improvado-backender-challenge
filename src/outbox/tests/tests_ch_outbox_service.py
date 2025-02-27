from typing import Callable
from unittest.mock import ANY, MagicMock, patch
from django.db import DatabaseError
import pytest
from core.base_model import Model
from outbox.models import EventLogOutbox
from outbox.services import ClickHouseOutboxService
from clickhouse_connect.driver import Client
from clickhouse_connect.driver.exceptions import ClickHouseError

pytestmark = pytest.mark.django_db


def test_save_events(f_event_instance_generator: Callable, num_of_events: int = 3):
    outbox_service = ClickHouseOutboxService()
    events = [event for event in f_event_instance_generator(num_of_events)]
    outbox_service.save_events(events)
    
    saved_events_qs = EventLogOutbox.unprocessed_objects.values_list(
        *outbox_service.migration_queryset_fields
    ).order_by('id')

    for db_record, event in zip(saved_events_qs, events, strict=True):
        assert db_record == ('some_event', 
                             ANY,
                             'Local',
                             event.model_dump_json(),
                             1)


def test_save_events_rolls_back_on_failure(f_event_instance: Model):
    outbox_service = ClickHouseOutboxService()
    
    assert not EventLogOutbox.objects.exists()

    with patch('outbox.services.EventLogOutbox.objects.bulk_create',
               side_effect=DatabaseError('Some db error')), \
        patch('outbox.services.capture_exception') as mock_sentry, \
        patch('outbox.services.logger.error') as mock_logger:

        with pytest.raises(DatabaseError, match='Some db error'):
            outbox_service.save_events(f_event_instance)

        assert not EventLogOutbox.objects.exists()

        mock_logger.assert_called_once()
        mock_sentry.assert_called_once()


@pytest.mark.parametrize(
    'f_populate_outbox',
    [3],
    indirect=True,
)
def test_migrate_events(
    f_populate_outbox,
    f_ch_client: Client,
    settings,
):
    settings.CLICKHOUSE_SCHEMA = settings.CLICKHOUSE_TEST_SCHEMA_NAME
    settings.OUTBOX_MIGRATION_MIN_BATCH_SIZE = 3
    settings.USE_TZ = False
    settings.TIME_ZONE = 'UTC'

    ch_log_table = settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME
    
    assert f_ch_client.command(f'SELECT count(*) FROM {ch_log_table}') == 0
    
    outbox_service = ClickHouseOutboxService()
    outbox_service.migrate_events()

    processed_events_qs = (
        EventLogOutbox.objects.filter(is_processed=True)
        .values_list(*outbox_service.migration_queryset_fields)
        .order_by('id')
    ) 

    ch_table_content = f_ch_client.query(f'SELECT * FROM {ch_log_table}')

    for outbox_record, ch_record in zip(
        processed_events_qs, ch_table_content.result_rows, strict=True
    ):
        assert outbox_record == ch_record


@pytest.mark.parametrize(
    'f_populate_outbox',
    [3],
    indirect=True,
)
def test_migrate_events_rolls_back_if_ch_insert_fails(
    f_populate_outbox,
    f_ch_client: Client,
    settings,
):
    settings.OUTBOX_MIGRATION_MIN_BATCH_SIZE = 3
    ch_log_table = settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME

    unprocessed_events_qs = EventLogOutbox.objects.filter(is_processed=False)
    unprocessed_count = unprocessed_events_qs.count()

    assert f_ch_client.command(f'SELECT count(*) FROM {ch_log_table}') == 0
    
    outbox_service = ClickHouseOutboxService()
    
    mock_ch_client = MagicMock()
    mock_ch_client.insert.side_effect = ClickHouseError('Some CH error')

    mock_init = MagicMock()
    mock_init.__enter__.return_value = mock_ch_client
    mock_init.__exit__.return_value = None
    
    with patch.object(outbox_service.event_log_client, 'init', return_value=mock_init), \
        patch('outbox.services.capture_exception') as mock_sentry, \
        patch('outbox.services.logger.error') as mock_logger:

        with pytest.raises(ClickHouseError, match='Some CH error'):
            outbox_service.migrate_events()

        mock_logger.assert_called_once()
        mock_sentry.assert_called_once()

    assert f_ch_client.command(f'SELECT count(*) FROM {ch_log_table}') == 0
    assert unprocessed_events_qs.count() == unprocessed_count
    
