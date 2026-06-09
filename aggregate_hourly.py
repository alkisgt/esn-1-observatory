#!/usr/bin/env python3
"""
Collapse the full-resolution data.csv into a small hourly.csv.

Why: the raw archive logs every few seconds (tens of MB and growing). The dashboard
only needs hourly resolution for the skill test, so we pre-aggregate on the server and
let the browser download a tiny file instead of the whole archive.

Input : data.csv   (columns: timestamp,value,id)
Output: hourly.csv (columns: timestamp,value,n)  -- timestamp = start of the UTC hour,
        value = mean of that hour, n = how many raw samples it averaged.

Stdlib only.
"""

import csv
from collections import defaultdict
from datetime import datetime, timezone

IN = "data.csv"
OUT = "hourly.csv"


def parse(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def main():
    buckets = defaultdict(lambda: [0.0, 0])  # hour_key -> [sum, count]
    rows = 0
    with open(IN, newline="") as f:
        for row in csv.DictReader(f):
            try:
                t = parse(row["timestamp"])
                v = float(row["value"])
            except (ValueError, KeyError, TypeError):
                continue
            hour = t.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
            key = hour.strftime("%Y-%m-%dT%H:00:00Z")
            buckets[key][0] += v
            buckets[key][1] += 1
            rows += 1

    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "value", "n"])
        for key in sorted(buckets):
            s, n = buckets[key]
            w.writerow([key, round(s / n, 4), n])

    print(f"Aggregated {rows} raw samples into {len(buckets)} hourly points.")


if __name__ == "__main__":
    main()
