from django.core.management.base import BaseCommand

from notifications.services.mnotify_service import MNotifyService


class Command(BaseCommand):
    help = "Check the current SMS balance from mNotify"

    def handle(self, *args, **options):
        mnotify = MNotifyService()
        result = mnotify.check_balance()

        if result["success"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"SMS Balance: {result['balance']} {result['currency']}"
                )
            )
            if "raw_response" in result:
                self.stdout.write(f"Raw response: {result['raw_response']}")
        else:
            self.stderr.write(
                self.style.ERROR(
                    f"Failed to check balance: {result.get('error', 'Unknown error')} "
                    f"(Code: {result.get('code', 'UNKNOWN')})"
                )
            )
