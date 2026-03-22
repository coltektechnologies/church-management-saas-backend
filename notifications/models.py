import json
import uuid

from django.db import models
from django.db.models import JSONField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import Church, User
from members.models import Member


class NotificationTemplate(models.Model):
    """Notification templates for reusable messages"""

    TEMPLATE_TYPE_CHOICES = [
        ("SMS", "SMS"),
        ("EMAIL", "Email"),
        ("IN_APP", "In-App"),
        ("ALL", "All Channels"),
    ]

    CATEGORY_CHOICES = [
        ("ANNOUNCEMENT", "Announcement"),
        ("REMINDER", "Reminder"),
        ("BIRTHDAY", "Birthday"),
        ("EVENT", "Event"),
        ("FINANCE", "Finance"),
        ("GENERAL", "General"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="notification_templates",
        db_column="church_id",
        null=True,
        blank=True,  # NULL for system-wide templates
    )

    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)

    # Template content
    subject = models.CharField(max_length=200, blank=True, null=True)  # For email
    message = models.TextField()  # Supports variables like {name}, {date}, etc.

    is_system_template = models.BooleanField(default=False)  # System vs user-created
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_templates"
        verbose_name = _("Notification Template")
        verbose_name_plural = _("Notification Templates")
        indexes = [
            models.Index(fields=["church", "category"]),
            models.Index(fields=["template_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.template_type})"


class Notification(models.Model):
    """In-app notifications"""

    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("READ", "Read"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="church_id",
    )

    # Recipient
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="user_id",
        null=True,
        blank=True,
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="member_id",
        null=True,
        blank=True,
    )

    # Content
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(
        max_length=20, choices=PRIORITY_CHOICES, default="MEDIUM"
    )
    category = models.CharField(max_length=50, blank=True, null=True)

    # Metadata
    link = models.URLField(blank=True, null=True)  # Link to related content
    icon = models.CharField(max_length=50, blank=True, null=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notifications"
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["church", "user", "is_read"]),
            models.Index(fields=["status", "scheduled_for"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        recipient = (
            self.user.username
            if self.user
            else self.member.full_name if self.member else "Unknown"
        )
        return f"{self.title} to {recipient}"


class SMSLog(models.Model):
    """SMS message log with mNotify integration"""

    class Meta:
        verbose_name = "Quick Message"
        verbose_name_plural = "Quick Messages"

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PENDING", "Pending"),
        ("QUEUED", "Queued"),
        ("SENT", "Sent"),
        ("DELIVERED", "Delivered"),
        ("FAILED", "Failed"),
        ("REJECTED", "Rejected"),
    ]

    GATEWAY_CHOICES = [
        ("MNOTIFY", "mNotify"),
        ("AFRICASTALKING", "Africa's Talking"),
        ("TWILIO", "Twilio"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="sms_logs",
        db_column="church_id",
        verbose_name=_("Church"),
    )

    # Recipient information
    phone_number = models.CharField(_("Phone Number"), max_length=20, db_index=True)
    member = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="member_id",
        verbose_name=_("Member"),
    )

    # Message content
    message = models.TextField(_("Message"))
    message_length = models.PositiveIntegerField(_("Message Length"), default=0)
    sms_count = models.PositiveIntegerField(_("SMS Count"), default=1)

    # Gateway information
    gateway = models.CharField(
        _("Gateway"),
        max_length=20,
        choices=GATEWAY_CHOICES,
        default="MNOTIFY",
        db_index=True,
    )
    gateway_message_id = models.CharField(
        _("Gateway Message ID"), max_length=200, blank=True, null=True, db_index=True
    )

    # Status tracking
    DIRECTION_CHOICES = [
        ("INBOUND", "Inbound"),
        ("OUTBOUND", "Outbound"),
    ]

    direction = models.CharField(
        _("Direction"),
        max_length=10,
        choices=DIRECTION_CHOICES,
        default="OUTBOUND",
        db_index=True,
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT",
        db_index=True,
    )
    delivery_status = models.CharField(
        _("Delivery Status"), max_length=100, blank=True, null=True
    )
    error_message = models.TextField(_("Error Message"), blank=True, null=True)

    # Financial tracking
    cost = models.DecimalField(
        _("Cost"), max_digits=10, decimal_places=4, null=True, blank=True
    )
    price_unit = models.CharField(
        _("Price Unit"),
        max_length=3,
        default="GHS",  # Ghanaian Cedi
        help_text=_("Currency code for the cost (e.g., GHS, USD)"),
    )

    # Timestamps
    scheduled_for = models.DateTimeField(
        _("Scheduled For"), null=True, blank=True, db_index=True
    )
    sent_at = models.DateTimeField(_("Sent At"), null=True, blank=True, db_index=True)
    delivered_at = models.DateTimeField(
        _("Delivered At"), null=True, blank=True, db_index=True
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        db_table = "sms_logs"  # Explicitly set the database table name
        verbose_name = _("SMS Log")
        verbose_name_plural = _("SMS Logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_for"]),
            models.Index(fields=["phone_number", "church"]),
            models.Index(
                fields=["phone_number"], name="notificatio_phone_n_a773e0_idx"
            ),
            models.Index(
                fields=["gateway_message_id"], name="notificatio_gateway_d43fee_idx"
            ),
        ]

    def __str__(self):
        return f"Quick Message to {self.phone_number} - {self.status}"

    def send(self):
        """
        Send the SMS using the configured gateway
        """
        import logging

        from notifications.services.sms_service import MNotifySMS

        # Set up logging
        logger = logging.getLogger(__name__)

        # Validate message is not empty
        if not self.message or not self.message.strip():
            error_msg = "Message cannot be empty"
            logger.error(f"SMS send failed: {error_msg}")
            self.status = "FAILED"
            self.error_message = error_msg
            self.save(update_fields=["status", "error_message", "updated_at"])
            return False

        try:
            logger.info(f"Attempting to send SMS to {self.phone_number}")
            logger.debug(f"Message content: {self.message[:100]}...")

            sms_service = MNotifySMS()

            # Prepare the message data
            message_data = {
                "recipients": [self.phone_number],
                "message": self.message,
                "sender_id": "ChurchSAAS",
                "scheduled_date": (
                    self.scheduled_for.isoformat() if self.scheduled_for else None
                ),
            }

            logger.debug(f"Prepared message data: {message_data}")

            # Send the message
            logger.info("Calling mNotify API...")
            result = sms_service.send_quick_sms(
                recipients=message_data["recipients"],
                message=message_data["message"],
                is_schedule=bool(message_data["scheduled_date"]),
                schedule_date=self.scheduled_for if self.scheduled_for else None,
            )

            # Log the raw API response
            logger.info("mNotify API Response:")
            logger.info("----------------------")
            for key, value in result.items():
                logger.info(f"{key}: {value}")
            logger.info("----------------------")

            # Update the status based on the result
            if result.get("status") == "success":
                status = "SENT" if not self.scheduled_for else "SCHEDULED"
                logger.info(
                    f'Message {status} successfully. Gateway ID: {result.get("message_id")}'
                )
                self.status = status
                self.gateway_message_id = result.get("message_id")
                self.sent_at = timezone.now()
                self.save(
                    update_fields=[
                        "status",
                        "gateway_message_id",
                        "sent_at",
                        "updated_at",
                    ]
                )
                return True
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error(f"Failed to send message. Error: {error_msg}")
                self.status = "FAILED"
                self.error_message = error_msg
                self.save(update_fields=["status", "error_message", "updated_at"])
                return False

        except Exception as e:
            logger.exception("Exception occurred while sending SMS:")
            self.status = "FAILED"
            self.error_message = str(e)
            self.save(update_fields=["status", "error_message", "updated_at"])
            return False


class EmailLog(models.Model):
    """Email message log"""

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("QUEUED", "Queued"),
        ("SENT", "Sent"),
        ("DELIVERED", "Delivered"),
        ("OPENED", "Opened"),
        ("CLICKED", "Clicked"),
        ("BOUNCED", "Bounced"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="email_logs",
        db_column="church_id",
    )

    # Recipient
    email_address = models.EmailField()
    member = models.ForeignKey(
        Member, on_delete=models.SET_NULL, null=True, blank=True, db_column="member_id"
    )

    # Content
    subject = models.CharField(max_length=200)
    message_html = models.TextField(null=True, blank=True)
    message_plain = models.TextField(blank=True, null=True)

    # Attachments
    has_attachments = models.BooleanField(default=False)
    attachment_urls = models.JSONField(null=True, blank=True)

    # Gateway details
    gateway = models.CharField(max_length=50, default="sendgrid")  # sendgrid, smtp
    gateway_message_id = models.CharField(max_length=200, blank=True, null=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    error_message = models.TextField(blank=True, null=True)

    # Tracking
    opened_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    first_opened_at = models.DateTimeField(null=True, blank=True)
    last_opened_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "email_logs"
        verbose_name = _("Email Log")
        verbose_name_plural = _("Email Logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["church", "status"]),
            models.Index(fields=["email_address"]),
            models.Index(fields=["gateway_message_id"]),
        ]

    def __str__(self):
        return f"Email to {self.email_address} - {self.subject}"


class NotificationPreference(models.Model):
    """User notification preferences"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
        db_column="user_id",
    )

    # Channel preferences
    enable_in_app = models.BooleanField(default=True)
    enable_email = models.BooleanField(default=True)
    enable_sms = models.BooleanField(default=True)

    # Category preferences
    announcements = models.BooleanField(default=True)
    reminders = models.BooleanField(default=True)
    birthdays = models.BooleanField(default=True)
    events = models.BooleanField(default=True)
    finance = models.BooleanField(default=True)

    # Frequency preferences
    digest_mode = models.BooleanField(default=False)  # Batch notifications
    digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ("DAILY", "Daily"),
            ("WEEKLY", "Weekly"),
        ],
        default="DAILY",
        blank=True,
        null=True,
    )

    # Quiet hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)  # e.g., 22:00
    quiet_hours_end = models.TimeField(null=True, blank=True)  # e.g., 07:00

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_preferences"
        verbose_name = _("Notification Preference")
        verbose_name_plural = _("Notification Preferences")

    def __str__(self):
        return f"Preferences for {self.user.username}"


class SMSDeliveryReport(models.Model):
    """Track delivery status of SMS messages"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("delivered", "Delivered"),
        ("failed", "Failed"),
        ("undelivered", "Undelivered"),
        ("rejected", "Rejected"),
    ]

    sms_log = models.OneToOneField(
        "SMSLog",
        on_delete=models.CASCADE,
        related_name="delivery_report",
        verbose_name=_("SMS Log"),
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    status_code = models.CharField(
        _("Status Code"), max_length=10, blank=True, null=True
    )
    status_message = models.TextField(_("Status Message"), blank=True, null=True)
    delivery_timestamp = models.DateTimeField(
        _("Delivery Timestamp"), blank=True, null=True
    )
    retry_count = models.PositiveIntegerField(_("Retry Count"), default=0)
    last_retry = models.DateTimeField(_("Last Retry"), blank=True, null=True)
    gateway_response = JSONField(_("Gateway Response"), null=True, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("SMS Delivery Report")
        verbose_name_plural = _("SMS Delivery Reports")
        ordering = ["-delivery_timestamp", "-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["delivery_timestamp"]),
        ]

    def __str__(self):
        return f"Report for SMS {self.sms_log_id} - {self.get_status_display()}"

    def log_retry_attempt(self, success=True, message=None, gateway_response=None):
        """Log a retry attempt"""
        self.retry_count += 1
        self.last_retry = timezone.now()
        if gateway_response:
            self.gateway_response = gateway_response
        if message:
            self.status_message = message
        if success:
            self.status = "pending"  # Reset status for next check
        self.save(
            update_fields=[
                "retry_count",
                "last_retry",
                "status",
                "status_message",
                "gateway_response",
                "updated_at",
            ]
        )
        return self


class NotificationBatch(models.Model):
    """Batch notification jobs"""

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="notification_batches",
        db_column="church_id",
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    # Target audience
    target_all_members = models.BooleanField(default=False)
    target_departments = models.JSONField(
        null=True, blank=True
    )  # List of department IDs
    target_members = models.JSONField(null=True, blank=True)  # List of member IDs

    # Content
    template = models.ForeignKey(
        NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    message = models.TextField()

    # Channels
    send_sms = models.BooleanField(default=False)
    send_email = models.BooleanField(default=False)
    send_in_app = models.BooleanField(default=False)

    # Progress tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    total_recipients = models.IntegerField(default=0)
    successful_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    # Scheduling
    scheduled_for = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_batches"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_batches"
        verbose_name = _("Notification Batch")
        verbose_name_plural = _("Notification Batches")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.status}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_status = None

        if not is_new:
            try:
                old_instance = NotificationBatch.objects.get(pk=self.pk)
                old_status = old_instance.status
            except NotificationBatch.DoesNotExist:
                pass

        # Save the instance first
        super().save(*args, **kwargs)

        # If this is a new batch or status changed to PENDING, and it's scheduled for now or in the past
        if (
            (is_new or old_status != "PENDING")
            and self.status == "PENDING"
            and (not self.scheduled_for or self.scheduled_for <= timezone.now())
        ):
            self.process()

    def process(self):
        """Process this notification batch asynchronously"""
        from django_rq import enqueue

        from notifications.management.commands.process_notification_batches import \
            process_batch

        # Update status to PROCESSING
        self.status = "PROCESSING"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at", "updated_at"])

        # Enqueue the processing task
        enqueue(process_batch, self.id)


class RecurringNotificationSchedule(models.Model):
    """
    Recurring notification schedule (Google Meet–style).
    Sends the same notification at a user-defined cadence: daily, weekly (specific days),
    monthly (specific day of month), or yearly (specific date).
    """

    FREQUENCY_CHOICES = [
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
        ("YEARLY", "Yearly"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        Church,
        on_delete=models.CASCADE,
        related_name="recurring_notification_schedules",
        db_column="church_id",
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    # Content (same as NotificationBatch)
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_schedules",
    )
    message = models.TextField()

    # Target audience
    target_all_members = models.BooleanField(default=False)
    target_departments = models.JSONField(
        null=True, blank=True
    )  # List of department UUIDs
    target_members = models.JSONField(null=True, blank=True)  # List of member UUIDs

    # Channels
    send_sms = models.BooleanField(default=False)
    send_email = models.BooleanField(default=False)
    send_in_app = models.BooleanField(default=False)

    # Recurrence
    frequency = models.CharField(
        max_length=20, choices=FREQUENCY_CHOICES, default="WEEKLY"
    )
    interval = models.PositiveIntegerField(
        default=1,
        help_text="Every N days/weeks/months/years (e.g. 2 = every 2 weeks)",
    )
    time_of_day = models.TimeField(
        help_text="Time of day to send (e.g. 12:00 for noon)",
    )

    # Weekly: which weekdays (0=Monday, 6=Sunday). Stored as JSON list e.g. [0,2,4]
    weekdays = models.JSONField(
        null=True,
        blank=True,
        help_text="For WEEKLY: list of weekdays 0-6 (0=Mon, 6=Sun). E.g. [2] = Wednesday.",
    )

    # Monthly: day of month (1-31)
    month_day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="For MONTHLY: day of month (1-31).",
    )

    # Yearly: month (1-12) and day of month (1-31)
    year_month = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="For YEARLY: month (1-12)."
    )
    year_month_day = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="For YEARLY: day of month (1-31)."
    )

    # Window
    start_date = models.DateField(
        help_text="First run on or after this date.",
    )
    end_date = models.DateField(null=True, blank=True)
    end_after_occurrences = models.PositiveIntegerField(
        null=True, blank=True, help_text="Stop after this many sends (optional)."
    )

    # Execution state
    next_run_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next scheduled run (computed and updated after each send).",
    )
    last_run_at = models.DateTimeField(null=True, blank=True)
    occurrence_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_notification_schedules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recurring_notification_schedules"
        verbose_name = _("Recurring Notification Schedule")
        verbose_name_plural = _("Recurring Notification Schedules")
        ordering = ["next_run_at"]

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"

    def save(self, *args, **kwargs):
        """Set next_run_at when active and not yet set (first save)."""
        if (
            self.is_active
            and self.next_run_at is None
            and not self.last_run_at
            and self.start_date
            and self.time_of_day
        ):
            from notifications.recurrence import get_next_run_at

            self.next_run_at = get_next_run_at(self)
        super().save(*args, **kwargs)
