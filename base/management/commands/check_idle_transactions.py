"""
Report PostgreSQL sessions stuck in idle in transaction.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "List PostgreSQL sessions that are idle in transaction."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-idle-seconds",
            type=int,
            default=30,
            help="Only show sessions idle longer than this many seconds (default: 30).",
        )
        parser.add_argument(
            "--terminate",
            action="store_true",
            help="Terminate matching backend PIDs (use with care).",
        )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write("This command only applies to PostgreSQL.")
            return

        min_idle = options["min_idle_seconds"]
        sql = """
            SELECT pid,
                   usename,
                   datname,
                   application_name,
                   state,
                   now() - state_change AS idle_for,
                   left(query, 120) AS query
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND state = 'idle in transaction'
              AND now() - state_change > make_interval(secs => %s)
            ORDER BY state_change
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, [min_idle])
            rows = cursor.fetchall()

        if not rows:
            self.stdout.write(self.style.SUCCESS("No idle-in-transaction sessions found."))
            return

        self.stdout.write(
            self.style.WARNING(f"Found {len(rows)} idle-in-transaction session(s):")
        )
        for row in rows:
            pid, user, db, app, state, idle_for, query = row
            self.stdout.write(
                f"  pid={pid} user={user} db={db} app={app!r} "
                f"idle_for={idle_for} query={query!r}"
            )
            if options["terminate"]:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_terminate_backend(%s)", [pid])
                    terminated = cursor.fetchone()[0]
                if terminated:
                    self.stdout.write(self.style.SUCCESS(f"    terminated pid={pid}"))
                else:
                    self.stdout.write(self.style.ERROR(f"    failed to terminate pid={pid}"))
