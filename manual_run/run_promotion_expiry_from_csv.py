#!/usr/bin/env python3
"""Run Promotion Expiry rules locally using a CSV from manual_run.

This script reads the CSV, builds CampaignWorkMessage objects and
invokes the promotion expiry helpers to build NotifyNow payloads, then
writes one JSON payload per line to a jsonl file for inspection.

Usage:
  python manual_run/run_promotion_expiry_from_csv.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from uuid import uuid4
import argparse


ROOT = Path(__file__).resolve().parents[1]

# Ensure bill_variance_domain package modules are importable when running
sys.path.insert(0, str(ROOT / "bill_variance_domain"))

import os

local_settings_file = Path(ROOT / "bill_variance_domain" / "local.settings.json")
if local_settings_file.exists():
    try:
        cfg = json.loads(local_settings_file.read_text(encoding="utf-8"))
        values = cfg.get("Values", {}) or {}
        for key, val in values.items():
            if key not in os.environ and val is not None:
                os.environ[key] = str(val)
    except Exception:
        pass

from shared_packages.campaign_models import CampaignWorkMessage

from campaigns.promotion_expiry import rules as promotion_rules


def parse_promo_details(value: str):
    if not value:
        return []

    try:
        return json.loads(value)
    except Exception:
        try:
            fixed = value.replace('""', '"')
            return json.loads(fixed)
        except Exception:
            return [value]


def row_to_source_context(row: dict[str, str]) -> dict:
    ctx: dict[str, object] = {k.upper(): v for k, v in row.items()}

    if "PROMO_DETAILS" in ctx:
        ctx["PROMO_DETAILS"] = parse_promo_details(ctx["PROMO_DETAILS"] or "")

    return ctx


def build_work(source_context: dict) -> CampaignWorkMessage:
    ban = source_context.get("BAN", "")
    run_id = f"manual-run-{uuid4()}"

    work = CampaignWorkMessage(
        run_id=run_id,
        campaign_id=promotion_rules.CAMPAIGN_ID,
        domain="bill_variance_domain",
        ban=ban,
        account_id=source_context.get("ACCT_ID", ""),
        idempotency_key=f"{run_id}:{promotion_rules.CAMPAIGN_ID}:{ban}",
        source_context=source_context,
        manual_run=True,
    )

    return work


def main():
    parser = argparse.ArgumentParser()
    default_csv = Path(__file__).resolve().parent / "promo_expiry_2026-09-07_testdata.csv"
    parser.add_argument("csv_path", nargs="?", default=str(default_csv))
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rows processed (0 = all)")
    args = parser.parse_args()

    csv_file = Path(args.csv_path)
    if not csv_file.exists():
        print(f"CSV file not found: {csv_file}")
        raise SystemExit(1)

    from datetime import datetime
    now = datetime.now()
    manual_filename = f"manual_promotion_expiry_{now.strftime('%Y%m%dT%H%M%S')}.jsonl"

    print(f"Processing CSV: {csv_file}")

    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / manual_filename

    with csv_file.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        count = 0
        for row in reader:
            if args.limit and count >= args.limit:
                break

            source_context = row_to_source_context(row)
            source_context["MANUAL_RUN_FILE"] = manual_filename
            work = build_work(source_context)

            print(f"Building promotion expiry payloads for BAN={work.ban} run_id={work.run_id}")

            try:
                # Build supporting pieces using rules helpers
                acct_info = promotion_rules._get_acct_info(source_context)
                promo_list = promotion_rules._build_promo_list(source_context)
                contact_info = promotion_rules._get_customer_contact_info(source_context)

                # Write email payload if available
                if contact_info.get("email"):
                    payload = promotion_rules._build_notifynow_payload(
                        work, promo_list, acct_info, contact_info, "email"
                    )
                    with out_file.open("a", encoding="utf-8") as ofh:
                        ofh.write(json.dumps(payload) + "\n")
                    print(f"WROTE MANUAL FILE: {out_file} (email)")

                # Write sms payload if available
                if contact_info.get("phone"):
                    payload = promotion_rules._build_notifynow_payload(
                        work, promo_list, acct_info, contact_info, "sms"
                    )
                    with out_file.open("a", encoding="utf-8") as ofh:
                        ofh.write(json.dumps(payload) + "\n")
                    print(f"WROTE MANUAL FILE: {out_file} (sms)")

            except Exception as exc:
                print(f"Error building payloads for BAN={work.ban}: {exc}")

            count += 1

    print(f"Done. Wrote payloads for {count} rows to {out_file}")


if __name__ == "__main__":
    main()
