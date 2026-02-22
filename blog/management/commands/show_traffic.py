"""
Show site traffic stats from Nginx access logs.

Usage (run on the server):
    python manage.py show_traffic              # Today's traffic
    python manage.py show_traffic --days 7     # Last 7 days
    python manage.py show_traffic --days 30    # Last 30 days
"""

import re
import os
import subprocess
from datetime import datetime, timedelta
from collections import Counter
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Show site traffic stats from Nginx access logs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=1,
            help="Number of days to analyze (default: 1 = today)",
        )
        parser.add_argument(
            "--top", type=int, default=15,
            help="Number of top items to show (default: 15)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        top_n = options["top"]

        # Try multiple log locations
        log_paths = [
            "/var/log/nginx/access.log",
            "/var/log/nginx/outfi_access.log",
        ]

        # Also try Docker logs
        lines = []
        for path in log_paths:
            if os.path.exists(path):
                with open(path, "r") as f:
                    lines = f.readlines()
                self.stdout.write(f"Reading from: {path}")
                break

        # If no file found, try Docker logs
        if not lines:
            try:
                result = subprocess.run(
                    ["docker", "logs", "--since", f"{days * 24}h", "nginx"],
                    capture_output=True, text=True, timeout=30,
                )
                lines = result.stdout.splitlines() + result.stderr.splitlines()
                self.stdout.write("Reading from: Docker nginx container logs")
            except Exception:
                pass

        if not lines:
            self.stdout.write(self.style.ERROR(
                "No access logs found. Run this on the production server."
            ))
            return

        # Parse log lines
        cutoff = datetime.now() - timedelta(days=days)
        
        # Nginx combined log format regex
        log_pattern = re.compile(
            r'(?P<ip>\S+) \S+ \S+ '
            r'\[(?P<date>[^\]]+)\] '
            r'"(?P<method>\S+)\s+(?P<path>\S+)\s+\S+" '
            r'(?P<status>\d+) (?P<size>\S+)'
        )

        page_views = Counter()
        unique_ips = set()
        status_codes = Counter()
        referrers = Counter()
        total_requests = 0
        bot_requests = 0
        human_requests = 0

        # Bot user agents
        bot_patterns = [
            "bot", "crawler", "spider", "slurp", "googlebot",
            "bingbot", "yandex", "baidu", "semrush", "ahrefs",
            "curl", "wget", "python-requests",
        ]

        for line in lines:
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="ignore")
            
            match = log_pattern.search(line)
            if not match:
                continue

            total_requests += 1
            ip = match.group("ip")
            path = match.group("path")
            status = match.group("status")

            # Check if bot
            line_lower = line.lower()
            is_bot = any(b in line_lower for b in bot_patterns)
            if is_bot:
                bot_requests += 1
            else:
                human_requests += 1

            unique_ips.add(ip)
            status_codes[status] += 1

            # Only count page views (not assets/API calls)
            if (
                not path.startswith("/assets/")
                and not path.startswith("/api/")
                and not path.startswith("/static/")
                and not path.startswith("/media/")
                and not path.endswith((".js", ".css", ".png", ".jpg", ".ico", ".woff2", ".map"))
                and status.startswith("2")
            ):
                page_views[path] += 1

        # ── Display Results ──
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"═══════════════════════════════════════════════════"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"  📊 Outfi Traffic Report — Last {days} day(s)"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"═══════════════════════════════════════════════════"
        ))

        self.stdout.write(f"\n  📈 Total Requests:    {total_requests:,}")
        self.stdout.write(f"  👤 Unique Visitors:   {len(unique_ips):,}")
        self.stdout.write(f"  🧑 Human Requests:    {human_requests:,}")
        self.stdout.write(f"  🤖 Bot Requests:      {bot_requests:,}")
        self.stdout.write(f"  📄 Page Views:        {sum(page_views.values()):,}")

        # Status codes
        self.stdout.write(f"\n  ── Status Codes ──")
        for code, count in sorted(status_codes.items()):
            emoji = "✅" if code.startswith("2") else "🔄" if code.startswith("3") else "⚠️"
            self.stdout.write(f"  {emoji} {code}: {count:,}")

        # Top pages
        self.stdout.write(f"\n  ── Top {top_n} Pages ──")
        for i, (path, count) in enumerate(page_views.most_common(top_n), 1):
            self.stdout.write(f"  {i:>3}. {count:>6,}  {path}")

        # Top visitors
        ip_counts = Counter()
        for line in lines:
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="ignore")
            match = log_pattern.search(line)
            if match:
                ip_counts[match.group("ip")] += 1

        self.stdout.write(f"\n  ── Top {min(10, len(ip_counts))} Visitors (by IP) ──")
        for i, (ip, count) in enumerate(ip_counts.most_common(10), 1):
            self.stdout.write(f"  {i:>3}. {count:>6,}  {ip}")

        self.stdout.write(f"\n  ── Summary ──")
        if human_requests > 0:
            bot_pct = (bot_requests / total_requests * 100) if total_requests else 0
            self.stdout.write(
                f"  Bot traffic: {bot_pct:.1f}% | "
                f"Human traffic: {100 - bot_pct:.1f}%"
            )
        self.stdout.write("")
