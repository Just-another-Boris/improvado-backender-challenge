from typing import Callable, Generator, Type
from django.conf import settings
import pytest
import pydantic
from core.base_model import Model
import uuid
from django.utils import timezone
from outbox.models import EventLogOutbox
from clickhouse_connect.driver import Client


@pytest.fixture(scope='function')
def f_event_model() -> Type[Model]:
    return pydantic.create_model(
        'SomeEvent',
        __base__=Model,
        foo=(str, 'foo'),
        bar=(int, 42),
        uid=(str, pydantic.Field(default_factory=lambda: uuid.uuid4().hex))
    )


@pytest.fixture(scope='function')
def f_event_instance(f_event_model: Type[Model]) -> Model:
    return f_event_model()


@pytest.fixture(scope='function')
def f_event_instance_generator(
    request: pytest.FixtureRequest,
    f_event_model: Type[Model],
) -> Callable[[int | None], Generator[Model]]:
    
    def _generator(count: int | None = None) -> Generator[Model]:
        count = count or getattr(request, 'param', 1)
        
        for _ in range(count):
            yield f_event_model()
    
    return _generator


@pytest.fixture(scope='function')
def f_populate_outbox(
    request: pytest.FixtureRequest,
    f_event_instance_generator: Callable
) -> Generator[list[EventLogOutbox]]:
    
    batch_size = getattr(request, 'param', 1)
    
    batch = [
        EventLogOutbox(
            event_type='some_event',
            event_date_time=timezone.now(),
            environment=settings.ENVIRONMENT,
            event_context=event.model_dump_json(),
        )
        for event in f_event_instance_generator(batch_size)
    ]
    
    created_objects = EventLogOutbox.objects.bulk_create(batch)
    yield created_objects


@pytest.fixture(autouse=True)
def f_clean_up_event_log(f_ch_client: Client) -> Generator:
    f_ch_client.query(
        f'TRUNCATE TABLE IF EXISTS {settings.CLICKHOUSE_EVENT_LOG_TABLE_NAME}'
    )
    yield
