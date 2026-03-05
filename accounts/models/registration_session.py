import uuid

from django.db import models
from django.utils import timezone


class RegistrationSession(models.Model):
    """
    Model to store multi-step registration data in the database.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step = models.PositiveSmallIntegerField(default=1)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "registration_sessions"
        indexes = [
            models.Index(fields=["expires_at"]),
            models.Index(fields=["step"]),
        ]

    def __str__(self):
        return f"Registration Session {self.id} (Step {self.step})"

    def is_expired(self):
        """Check if the session has expired."""
        return timezone.now() > self.expires_at
