"""
Azure SQL DB operational store (TDD Sections 3.1, 3.3, 6).

System of record for campaign runs, eligibility outcomes, suppression history,
handoff status, and reconciliation counts. Backs:
  - CampaignRun            (run metadata + counts)
  - AccountEligibilitySuppression  (per-account eligibility/suppression/handoff)
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
    # Connection (lazy; auto-reconnecting)
    # ------------------------------------------------------------------ #
    def _get_conn(self):
        if self.connection_string:
            try:
                import pyodbc  # imported lazily

                # If connection is missing or closed, reopen
                if self._conn is None:
                    self._conn = pyodbc.connect(self.connection_string, autocommit=True)
                    logger.info("Opened Azure SQL DB connection.")
            except Exception as exc:  # pragma: no cover - infra dependent
                logger.warning("Azure SQL DB connection unavailable: %s", exc)
                self._conn = None
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

        sql = """
        MERGE INTO dbo.CampaignRun AS target
        USING (SELECT ? AS run_id) AS source
        ON target.run_id = source.run_id
        WHEN MATCHED THEN
            UPDATE SET 
                status = ?,
                end_ts = ?,
                input_count = ?,
                eligible_count = ?,
                excluded_count = ?,
                suppressed_count = ?,
                error_count = ?
        WHEN NOT MATCHED THEN
            INSERT (run_id, campaign_id, status, start_ts, end_ts, input_count, eligible_count, excluded_count, suppressed_count, error_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql,
                    # MATCH parameters
                    run.run_id,
                    # UPDATE parameters
                    run.status, run.end_ts, run.input_count, run.eligible_count, 
                    run.excluded_count, run.suppressed_count, run.error_count,
                    # INSERT parameters
                    run.run_id, run.campaign_id, run.status, run.start_ts, run.end_ts,
                    run.input_count, run.eligible_count, run.excluded_count, 
                    run.suppressed_count, run.error_count
                )
            logger.info("CampaignRun upsert (SQL) run_id=%s status=%s", run.run_id, run.status)
        except Exception as exc:
            logger.error("Failed to upsert CampaignRun %s: %s", run.run_id, exc)

    # ------------------------------------------------------------------ #
    # AccountEligibilitySuppression
    # ------------------------------------------------------------------ #
    def upsert_eligibility(self, record: AudienceRecord) -> None:
        """Persist eligibility/exclusion/suppression/handoff outcome per account."""
        key = (record.campaign_id, record.ban)
        conn = self._get_conn()
        if conn is None:
            self._eligibility[key] = {
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
            logger.info(
                "Eligibility upsert (in-memory): campaign=%s ban=%s status=%s handoff=%s",
                record.campaign_id, record.ban,
                record.eligibility_status.value, record.handoff_status.value,
            )
            return

        sql = """
        MERGE INTO dbo.AccountEligibilitySuppression AS target
        USING (SELECT ? AS campaign_id, ? AS ban) AS source
        ON target.campaign_id = source.campaign_id AND target.ban = source.ban
        WHEN MATCHED THEN
            UPDATE SET 
                customer_id = ?,
                fan = ?,
                latest_run_id = ?,
                eligibility_status = ?,
                exclusion_reason = ?,
                suppression_reason = ?,
                handoff_status = ?,
                handoff_target = ?,
                handoff_error_code = ?,
                updated_ts = ?
        WHEN NOT MATCHED THEN
            INSERT (campaign_id, ban, customer_id, fan, latest_run_id, eligibility_status, exclusion_reason, suppression_reason, handoff_status, handoff_target, handoff_error_code, updated_ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql,
                    # ON clause keys
                    record.campaign_id, record.ban,
                    # UPDATE params
                    record.customer_id, record.fan, record.run_id, record.eligibility_status.value,
                    record.exclusion_reason, record.suppression_reason, record.handoff_status.value,
                    record.handoff_target, record.handoff_error_code, record.updated_ts,
                    # INSERT params
                    record.campaign_id, record.ban, record.customer_id, record.fan, record.run_id,
                    record.eligibility_status.value, record.exclusion_reason, record.suppression_reason,
                    record.handoff_status.value, record.handoff_target, record.handoff_error_code, record.updated_ts
                )
            logger.info("Eligibility upsert (SQL) campaign=%s ban=%s", record.campaign_id, record.ban)
        except Exception as exc:
            logger.error("Failed to upsert eligibility for ban %s: %s", record.ban, exc)

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

        sql = """
        UPDATE dbo.AccountEligibilitySuppression
        SET last_contacted_ts = ?,
            suppression_until_ts = ?,
            latest_run_id = ?,
            updated_ts = ?
        WHERE campaign_id = ? AND ban = ?;
        """

        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, now, until, run_id, now, campaign_id, ban)
            logger.info("Handoff stamp (SQL) campaign=%s ban=%s until=%s", campaign_id, ban, until)
        except Exception as exc:
            logger.error("Failed to stamp handoff for ban %s: %s", ban, exc)

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

        sql = """
        SELECT suppression_until_ts 
        FROM dbo.AccountEligibilitySuppression WITH (NOLOCK)
        WHERE campaign_id = ? AND ban = ?;
        """

        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, campaign_id, ban)
                row = cursor.fetchone()
                
                if row and row[0]:
                    suppression_until = row[0]
                    # Ensure timezone awareness comparison
                    if suppression_until.tzinfo is None:
                        suppression_until = suppression_until.replace(tzinfo=timezone.utc)

                    if suppression_until > datetime.now(timezone.utc):
                        return (True, "WITHIN_SUPPRESSION_WINDOW")
        except Exception as exc:
            logger.error("Failed to check suppression status for ban %s: %s", ban, exc)

        return (False, None)


@lru_cache(maxsize=1)
def get_sql_repository() -> SqlRepository:
    """Cached singleton for the process lifetime."""
    return SqlRepository()