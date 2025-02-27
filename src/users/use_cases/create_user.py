from typing import Any, Type

from django.conf import settings
from sentry_sdk import capture_exception
import structlog

from core.base_model import Model
from core.use_case import UseCase, UseCaseRequest, UseCaseResponse
from outbox.services import BaseOutboxService
from users.models import User
from django.db import transaction
from core.utils import get_class_by_full_path

logger = structlog.get_logger(__name__)


class UserCreated(Model):
    email: str
    first_name: str
    last_name: str


class CreateUserRequest(UseCaseRequest):
    email: str
    first_name: str = ''
    last_name: str = ''


class CreateUserResponse(UseCaseResponse):
    result: User | None = None
    error: str = ''


class CreateUser(UseCase):
    def __init__(
        self, outbox_service: Type[BaseOutboxService] | None = None, *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.outbox_service = (
            outbox_service 
            or get_class_by_full_path(settings.OUTBOX_DEFAULT_SERVICE_CLASS)
        )
        
    def _get_context_vars(self, request: UseCaseRequest) -> dict[str, Any]:
        return {
            'email': request.email,
            'first_name': request.first_name,
            'last_name': request.last_name,
        }

    def _execute(self, request: CreateUserRequest) -> CreateUserResponse:
        logger.info('creating a new user')
        
        try:
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    email=request.email,
                    defaults={
                        'first_name': request.first_name, 'last_name': request.last_name,
                    },
                )

                if created:
                    logger.info('user has been created')
                    self._log_event(user)
                    return CreateUserResponse(result=user)
        except Exception as e:
            logger.error(f'Error occurred. Transaction rolled back.', error=str(e))
            capture_exception(e)
            raise e
        
        logger.error(f'Unable to create a new user with emal {request.email}')
        return CreateUserResponse(error=f'User with this email already exists')

    def _log_event(self, user: User) -> None:
        event = UserCreated.model_validate(user)
        self.outbox_service().save_events(event)

        
