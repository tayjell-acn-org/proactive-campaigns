#!/usr/bin/env python3
"""Run Pending Credits rules locally using a CSV from manual_run.

This script reads the CSV, builds CampaignWorkMessage objects and invokes
the pending credits processor directly (bypassing Service Bus) so you can
test rules locally.

Usage:
  python manual_run/run_pending_credits_from_csv.py

Defaults to manual_run/pc-no-e_2026-09-03-1213_testdata.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from uuid import uuid4
import argparse


ROOT = Path(__file__).resolve().parents[1]

# Ensure bill_variance_domain package modules (shared_packages, campaigns, etc.)
# are imported when running this script from the repo root
sys.path.insert(0, str(ROOT / "bill_variance_domain"))

# Load local.settings.json into environment for local development so modules
# that read os.environ (FERNET_KEY, HMAC_SECRET, etc.) work when running the
# script outside the Functions host.
import os

local_settings_file = Path(ROOT / "bill_variance_domain" / "local.settings.json")
if local_settings_file.exists():
    try:
        cfg = json.loads(local_settings_file.read_text(encoding="utf-8"))
        values = cfg.get("Values", {}) or {}
        for key, val in values.items():
            # Do not overwrite any env vars already set in the shell
            if key not in os.environ and val is not None:
                os.environ[key] = str(val)
    except Exception as exc:
        print(f"Warning: failed to load local.settings.json: {exc}")

from shared_packages.campaign_models import CampaignWorkMessage

from campaigns.pending_credits import rules as pending_rules


def parse_credit_details(value: str):
    if not value:
        return []

    try:
        return json.loads(value)
    except Exception:
        # CSV may escape quotes; try replace then parse
        try:
            fixed = value.replace('""', '"')
            return json.loads(fixed)
        except Exception:
            # Last resort: return raw string inside a list
            return [value]


def row_to_source_context(row: dict[str, str]) -> dict:
    # Normalize keys to uppercase to match rules
    ctx: dict[str, object] = {k.upper(): v for k, v in row.items()}

    # Parse CREDIT_DETAILS field/JSON string into python list
    if "CREDIT_DETAILS" in ctx:
        ctx["CREDIT_DETAILS"] = parse_credit_details(ctx["CREDIT_DETAILS"] or "")

    return ctx


def build_work(source_context: dict) -> CampaignWorkMessage:
    ban = source_context.get("BAN", "")
    run_id = f"manual-run-{uuid4()}"

    work = CampaignWorkMessage(
        run_id=run_id,
        campaign_id=pending_rules.CAMPAIGN_ID,
        domain="bill_variance_domain",
        ban=ban,
        account_id=source_context.get("ACCT_ID", ""),
        idempotency_key=f"{run_id}:{pending_rules.CAMPAIGN_ID}:{ban}",
        source_context=source_context,
    )

    return work


def main():
    parser = argparse.ArgumentParser()
    default_csv = Path(__file__).resolve().parent / "pc-no-e_2026-09-03-1213_testdata.csv"
    parser.add_argument("csv_path", nargs="?", default=str(default_csv))
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rows processed (0 = all)")
    args = parser.parse_args()

    csv_file = Path(args.csv_path)
    if not csv_file.exists():
        print(f"CSV file not found: {csv_file}")
        raise SystemExit(1)

    print(f"Processing CSV: {csv_file}")

    with csv_file.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        count = 0
        for row in reader:
            if args.limit and count >= args.limit:
                break

            source_context = row_to_source_context(row)
            work = build_work(source_context)

            print(f"Invoking pending credits.process for BAN={work.ban} run_id={work.run_id}")

            try:
                pending_rules.process(work)
            except Exception as exc:
                print(f"Error processing BAN={work.ban}: {exc}")

            count += 1

    print(f"Done. Processed {count} rows.")


if __name__ == "__main__":
    main()
