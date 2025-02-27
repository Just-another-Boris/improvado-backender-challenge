import uuid
from collections.abc import Generator
from unittest.mock import ANY, patch

from django.db import DatabaseError
import pytest
from clickhouse_connect.driver import Client
from django.conf import settings

from outbox.consts import CH_EVENT_LOG_COLUMNS
from outbox.models import EventLogOutbox
from users.models import User
from users.use_cases import CreateUser, CreateUserRequest, UserCreated

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def f_use_case() -> CreateUser:
    return CreateUser()


@pytest.fixture()
def f_user_created_request() -> CreateUserRequest:
    return CreateUserRequest(
        email=f'test_{uuid.uuid4()}@email.com',
        first_name='Test',
        last_name='Testovich',
    )


@pytest.fixture(autouse=True)
def f_clean_up_event_log(f_ch_client: Client) -> Generator:
    f_ch_client.query(f'TRUNCATE TABLE {settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}')
    yield


def test_user_created(f_use_case: CreateUser, f_user_created_request):
    response = f_use_case.execute(f_user_created_request)

    assert response.result.email == f_user_created_request.email
    assert response.error == ''


def test_emails_are_unique(f_use_case: CreateUser, f_user_created_request):
    f_use_case.execute(f_user_created_request)
    response = f_use_case.execute(f_user_created_request)

    assert response.result is None
    assert response.error == 'User with this email already exists'


def test_user_created_event_saved(f_use_case: CreateUser, f_user_created_request):
    """Test asserts that a user created and a related event saved to outbox table."""
    
    user_created_events_qs = (
        EventLogOutbox.objects.filter(event_type='user_created')
        .values_list(*CH_EVENT_LOG_COLUMNS)
    )
    
    assert not user_created_events_qs.exists()

    user_created_event = (
        UserCreated(
            email=f_user_created_request.email, 
            first_name=f_user_created_request.first_name, 
            last_name=f_user_created_request.last_name,
        )
    )

    response = f_use_case.execute(f_user_created_request)

    assert response.result.email == f_user_created_request.email

    saved_events = list(user_created_events_qs)
    
    assert len(saved_events) == 1
    assert saved_events[0] == ('user_created',
                               ANY,
                               'Local',
                               user_created_event.model_dump_json(),
                               1)


def test_no_user_or_event_created_if_event_logging_fails(
    f_use_case: CreateUser, f_user_created_request: CreateUserRequest
):
    user_exists = User.objects.filter(email=f_user_created_request.email).exists()
    
    assert not user_exists
    assert EventLogOutbox.objects.count() == 0

    with patch.object(f_use_case, '_log_event', 
                      side_effect=DatabaseError('Some db error')), \
        patch('users.use_cases.create_user.capture_exception') as mock_sentry, \
        patch('users.use_cases.create_user.logger.error') as mock_logger:
        
        with pytest.raises(DatabaseError, match='Some db error'):
            f_use_case.execute(f_user_created_request)

        mock_logger.assert_called_once()
        mock_sentry.assert_called_once()
    
    assert not user_exists
    assert EventLogOutbox.objects.count() == 0
    

