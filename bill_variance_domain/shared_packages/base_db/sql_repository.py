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
import sqlite3
from datetime import datetime, UTC, timedelta
from functools import lru_cache
from typing import Optional

from shared_packages.campaign_models import AudienceRecord, CampaignRun

logger = logging.getLogger(__name__)


class SqlRepository:
    def __init__(self, connection_string: Optional[str] = None) -> None:
        ##self.connection_string = connection_string or os.getenv("SQL_CONNECTION_STRING")
        self.connection_string = "test"
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

    # ------------------------------------------------------------------ #
    # AccountEligibilitySuppression
    # ------------------------------------------------------------------ #
    def upsert_eligibility(self, record: AudienceRecord) -> None:
        """Persist eligibility/exclusion/suppression/handoff outcome per account."""

    def record_handoff(
        self,
        campaign_id: str,
        ban: str,
        run_id: str,
        suppression_window_days: int,
    ) -> None:
        """Stamp last-contacted + suppression-until after a successful handoff."""

    def is_suppressed(self, campaign_id: str, ban: str) -> tuple[bool, Optional[str]]:
        """
        Suppression check (TDD Step 3): returns (suppressed, reason).

        Checks the campaign-specific suppression window against last-contacted
        history in AccountEligibilitySuppression.
        """

        conn = sqlite3.connect("campaign.db")

        cursor = conn.cursor()

        suppression_date = (datetime.now(UTC) - timedelta(days=30)).isoformat()

        cursor.execute(
            """
            SELECT 1
            FROM AccountContactHistory
            WHERE CampaignCode = ?
            AND Ban = ?
            AND Status = 'CONTACTED'
            AND ContactDate >= ?
            LIMIT 1
        """,
            (campaign_id, ban, suppression_date),
        )

        result = cursor.fetchone()

        conn.close()
        
        suppresed = result is not None
        reason = "Hello"

        return suppresed, reason
    
    def record_contact(self, campaign_code: str, ban: str, channel_type: str, contact_value: str, transaction_id: str):

        now = datetime.now(UTC).isoformat()

        conn = sqlite3.connect("campaign.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO AccountContactHistory
            (
                CampaignCode,
                Ban,
                ChannelType,
                ContactValue,
                Status,
                ReasonCode,
                NotifyNowTransactionId,
                ContactDate,
                CreatedDate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                campaign_code,
                ban,
                channel_type,
                contact_value,
                "CONTACTED",
                None,
                transaction_id,
                now,
                now,
            ),
        )

        conn.commit()
        conn.close()


@lru_cache(maxsize=1)
def get_sql_repository() -> SqlRepository:
    """Cached singleton for the process lifetime."""
    return SqlRepository()
