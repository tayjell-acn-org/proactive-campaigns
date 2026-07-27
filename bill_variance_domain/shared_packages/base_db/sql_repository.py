"""
Azure SQL DB operational store (TDD Sections 3.1, 3.3, 6).

System of record for campaign runs, eligibility outcomes, suppression history,
handoff status, and reconciliation counts. Backs:
  - CampaignRun                    (run metadata + counts)
  - AccountEligibilitySuppression  (per-account eligibility/suppression/handoff)

This reference implementation logs the intended writes and keeps an in-memory
store so the pipeline runs end-to-end before the database is provisioned.
Replace the _execute()/query bodies with real pyodbc/SQLAlchemy calls (using a
Key Vault connection string or managed identity) once the DB is available.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

from shared_packages.campaign_models import AudienceRecord, CampaignRun

logger = logging.getLogger(__name__)


class SqlRepository:
    def __init__(self, connection_string: Optional[str] = None) -> None:
        self.connection_string = connection_string or os.getenv("SQL_CONNECTION_STRING")
        self._conn = None
        # In-memory fallback keyed by (campaign_id, ban) for local runs.
        self._eligibility: dict[tuple[str, str], dict] = {}

    # ------------------------------------------------------------------ #
    # Connection (lazy; only when a connection string is configured)
    # ------------------------------------------------------------------ #
    def _get_conn(self):
        if self._conn is None and self.connection_string:
            try:
                import pyodbc  # imported lazily

                self._conn = pyodbc.connect(self.connection_string)
                logger.info("Opened Azure SQL DB connection.")
            except Exception as exc:  # pragma: no cover - infra dependent
                logger.warning("Azure SQL DB connection unavailable: %s", exc)
        return self._conn

    # ------------------------------------------------------------------ #
    # CampaignRun
    # ------------------------------------------------------------------ #
    def upsert_campaign_run(self, run: CampaignRun) -> None:
        """Persist run metadata + reconciliation counts (TDD Sections 6.1, 8.1 step 9)."""
        conn = self._get_conn()
        if conn is None:
            logger.info(
                "CampaignRun upsert (in-memory): run_id=%s campaign=%s status=%s "
                "input=%s eligible=%s excluded=%s suppressed=%s errors=%s",
                run.run_id, run.campaign_id, run.status, run.input_count,
                run.eligible_count, run.excluded_count, run.suppressed_count, run.error_count,
            )
            return
        # TODO: real MERGE/UPSERT into CampaignRun table.
        logger.info("CampaignRun upsert (SQL) run_id=%s", run.run_id)

    # ------------------------------------------------------------------ #
    # AccountEligibilitySuppression
    # ------------------------------------------------------------------ #
    def upsert_eligibility(self, record: AudienceRecord) -> None:
        """Persist eligibility/exclusion/suppression/handoff outcome per account."""
        key = (record.campaign_id, record.ban)
        row = {
            "campaign_id": record.campaign_id,
            "customer_id": record.customer_id,
            "ban": record.ban,
            "fan": record.fan,
            "latest_run_id": record.run_id,
            "eligibility_status": record.eligibility_status.value,
            "exclusion_reason": record.exclusion_reason,
            "suppression_reason": record.suppression_reason,
            "handoff_status": record.handoff_status.value,
            "handoff_target": record.handoff_target,
            "handoff_error_code": record.handoff_error_code,
            "updated_ts": record.updated_ts,
        }
        conn = self._get_conn()
        if conn is None:
            self._eligibility[key] = row
            logger.info(
                "Eligibility upsert (in-memory): campaign=%s ban=%s status=%s handoff=%s",
                record.campaign_id, record.ban,
                record.eligibility_status.value, record.handoff_status.value,
            )
            return
        # TODO: real MERGE/UPSERT into AccountEligibilitySuppression table.
        logger.info("Eligibility upsert (SQL) campaign=%s ban=%s", record.campaign_id, record.ban)

    def record_handoff(
        self,
        campaign_id: str,
        ban: str,
        run_id: str,
        suppression_window_days: int,
    ) -> None:
        """Stamp last-contacted + suppression-until after a successful handoff."""
        now = datetime.now(timezone.utc)
        until = now + timedelta(days=suppression_window_days)
        conn = self._get_conn()
        if conn is None:
            row = self._eligibility.get((campaign_id, ban), {})
            row["last_contacted_ts"] = now.isoformat()
            row["suppression_until_ts"] = until.isoformat()
            self._eligibility[(campaign_id, ban)] = row
            logger.info(
                "Handoff stamp (in-memory): campaign=%s ban=%s suppress_until=%s",
                campaign_id, ban, until.isoformat(),
            )
            return
        # TODO: real UPDATE of last_contacted_ts / suppression_until_ts.
        logger.info("Handoff stamp (SQL) campaign=%s ban=%s", campaign_id, ban)

    def is_suppressed(self, campaign_id: str, ban: str) -> tuple[bool, Optional[str]]:
        """
        Suppression check (TDD Step 3): returns (suppressed, reason).

        Checks the campaign-specific suppression window against last-contacted
        history in AccountEligibilitySuppression.
        """
        conn = self._get_conn()
        if conn is None:
            row = self._eligibility.get((campaign_id, ban))
            if not row:
                return (False, None)
            until = row.get("suppression_until_ts")
            if until and datetime.fromisoformat(until) > datetime.now(timezone.utc):
                return (True, "WITHIN_SUPPRESSION_WINDOW")
            return (False, None)
        # TODO: real SELECT against AccountEligibilitySuppression.
        return (False, None)


@lru_cache(maxsize=1)
def get_sql_repository() -> SqlRepository:
    """Cached singleton for the process lifetime."""
    return SqlRepository()
