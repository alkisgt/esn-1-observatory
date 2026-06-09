#!/usr/bin/env python3
"""
Harvest sensor data from Adafruit IO and append it to data.csv (a permanent archive).

Designed to run inside GitHub Actions on a schedule. Uses ONLY the Python standard
library, so the workflow needs no `pip install` step.

Reads three environment variables (set by the workflow):
    AIO_USER  - your Adafruit IO username        (e.g. alkisgt)
    AIO_FEED  - the feed key to archive           (e.g. mv-signal)
    AIO_KEY   - your Adafruit IO key  (provided from a GitHub Actions *Secret*)

Behaviour:
    * First run (no data.csv): pulls everything Adafruit still has (last 30 days).
    * Every later run: pulls only what is newer than the last archived point.
    * De-duplicates by the Adafruit point id, so overlaps are harmless.
    * Writes data.csv sorted by time, columns: timestamp,value,id
"""

import os
import csv
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

USER = os.environ["AIO_USER"]
FEED = os.environ["AIO_FEED"]
KEY = os.environ["AIO_KEY"]

CSV_PATH = "data.csv"
BACKFILL_DAYS = 30   # first run: how far back to pull (Adafruit free keeps 30 days)
PAGE = 1000          # Adafruit max points per request


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fetch(start, end):
    """Fetch every point in [start, end], paging backwards by end_time."""
    out, cursor = [], end
    while True:
        q = urllib.parse.urlencode({
            "start_time": iso(start),
            "end_time": iso(cursor),
            "limit": PAGE,
        })
        url = f"https://io.adafruit.com/api/v2/{USER}/feeds/{FEED}/data?{q}"
        req = urllib.request.Request(url, headers={"X-AIO-Key": KEY})
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.load(r)
        if not page:
            break
        out.extend(page)
        if len(page) < PAGE:
            break
        # Adafruit returns newest-first; step the cursor just before the oldest one.
        oldest = min(parse(p["created_at"]) for p in page)
        nxt = oldest - timedelta(seconds=1)
        if nxt <= start:
            break
        cursor = nxt
    return out


def load_existing():
    rows, seen = [], set()
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)
                seen.add(row["id"])
    return rows, seen


def main():
    rows, seen = load_existing()
    if rows:
        last = max(parse(r["timestamp"]) for r in rows)
        start = last - timedelta(minutes=5)   # small overlap; dedup handles it
    else:
        start = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)
    end = datetime.now(timezone.utc)

    points = fetch(start, end)
    added = 0
    for p in points:
        pid = str(p.get("id", ""))
        if pid and pid in seen:
            continue
        rows.append({
            "timestamp": p["created_at"].replace("+00:00", "Z"),
            "value": p.get("value", ""),
            "id": pid,
        })
        seen.add(pid)
        added += 1

    rows.sort(key=lambda r: r["timestamp"])
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "value", "id"])
        w.writeheader()
        w.writerows(rows)

    print(f"Fetched {len(points)} points, added {added} new. Total rows now: {len(rows)}.")


if __name__ == "__main__":
    main()
