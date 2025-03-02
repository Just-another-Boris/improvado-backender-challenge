from django.db import models

from core.models import TimeStampedModel
from outbox.managers import UnprocessedEventsManager


class EventLogOutbox(TimeStampedModel):
    is_processed = models.BooleanField(null=False, default=False)
    event_type = models.CharField(null=False)
    event_date_time = models.DateTimeField(null=False)
    environment = models.CharField(null=False)
    event_context = models.TextField(null=False)
    metadata_version = models.IntegerField(null=False, default=1)

    objects = models.Manager()
    unprocessed_objects = UnprocessedEventsManager()

