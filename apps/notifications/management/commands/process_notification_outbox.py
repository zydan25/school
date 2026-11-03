"""Run the durable notification outbox as a supervised worker process."""
import os
import time

from django.core.management.base import BaseCommand, CommandError

from apps.notifications.services import process_outbox_batch


class Command(BaseCommand):
    help = "Process pending school notification and verified inbound-webhook events."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep polling until the process is stopped.")
        parser.add_argument("--batch-size", type=int, default=int(os.getenv("NOTIFICATION_OUTBOX_BATCH_SIZE", "50")))
        parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("NOTIFICATION_OUTBOX_POLL_SECONDS", "2")))

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        poll_seconds = options["poll_seconds"]
        if not 1 <= batch_size <= 500:
            raise CommandError("--batch-size must be between 1 and 500.")
        if not 0.2 <= poll_seconds <= 60:
            raise CommandError("--poll-seconds must be between 0.2 and 60.")
        while True:
            stats = process_outbox_batch(limit=batch_size)
            self.stdout.write(
                f"claimed={stats['claimed']} succeeded={stats['succeeded']} "
                f"retrying={stats['retrying']} failed={stats['failed']}"
            )
            if not options["loop"]:
                break
            if stats["claimed"] == 0:
                time.sleep(poll_seconds)
