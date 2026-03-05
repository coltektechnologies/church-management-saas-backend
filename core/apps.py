from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"
    verbose_name = "Core"

    def ready(self):
        # Register audit log signals
        from .signals import register_audit_handlers

        register_audit_handlers()

        # Import signals to register them
        from . import signals  # noqa
