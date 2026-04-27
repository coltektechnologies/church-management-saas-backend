from django.test import SimpleTestCase

from treasury.income_notifications import parse_income_notification_channels


class IncomeNotificationChannelParseTests(SimpleTestCase):
    def test_empty_notes(self):
        self.assertEqual(parse_income_notification_channels(None), (False, False))
        self.assertEqual(parse_income_notification_channels(""), (False, False))

    def test_no_marker(self):
        self.assertEqual(
            parse_income_notification_channels("Some detail only"), (False, False)
        )

    def test_sms_only(self):
        self.assertEqual(
            parse_income_notification_channels("x | Notifications: sms"), (True, False)
        )

    def test_email_and_both(self):
        self.assertEqual(
            parse_income_notification_channels("Notifications: email, other"),
            (False, True),
        )
        self.assertEqual(
            parse_income_notification_channels("Notifications: both"),
            (True, True),
        )

    def test_case_insensitive(self):
        self.assertEqual(
            parse_income_notification_channels("NOTIFICATIONS: SMS, Email"),
            (True, True),
        )
