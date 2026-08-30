"""Deliver what the queue holds.

Run on a schedule. Delivery is separated from the write that caused it so a
mail outage delays a notification rather than failing somebody's save.
"""
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from plinta.contrib.notifications.models import EmailStatus, QueuedEmail

#: After this many failures a message stops being retried. A queue that retries
#: for ever is a queue that never drains.
MAX_ATTEMPTS = 5


class Command(BaseCommand):
    help = "Send queued notification emails."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument(
            "--retry-failed", action="store_true",
            help="Include messages that failed but have attempts left.",
        )

    def handle(self, *args, **options):
        statuses = [EmailStatus.QUEUED]
        if options["retry_failed"]:
            statuses.append(EmailStatus.FAILED)

        pending = QueuedEmail.objects.filter(
            status__in=statuses, attempts__lt=MAX_ATTEMPTS
        )[: options["limit"]]

        sent = failed = 0
        for message in pending:
            message.attempts += 1
            try:
                send_mail(message.subject, message.body, None, [message.to])
            except Exception as exc:  # noqa: BLE001 - any backend, any failure
                message.status = EmailStatus.FAILED
                message.last_error = str(exc)[:500]
                failed += 1
            else:
                message.status = EmailStatus.SENT
                message.sent_at = timezone.now()
                message.last_error = ""
                sent += 1
            message.save(update_fields=["status", "attempts", "sent_at", "last_error"])

        self.stdout.write(f"sent {sent}, failed {failed}")
