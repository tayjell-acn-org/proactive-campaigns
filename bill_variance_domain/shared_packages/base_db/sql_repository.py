from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


class SqlRepository:
    def __init__(self, connection_string: Optional[str] = None) -> None:
        self.connection_string = connection_string or os.getenv("SQL_CONNECTION_STRING")
        self._conn = None

    def _get_conn(self):
        if not self.connection_string:
            raise RuntimeError("SQL_CONNECTION_STRING is not configured.")

        try:
            import pyodbc

            if self._conn is None:
                self._conn = pyodbc.connect(
                    self.connection_string,
                    autocommit=True,
                )
                logger.info("Opened Azure SQL DB connection.")

            self._conn.cursor().execute("SELECT 1")
            return self._conn
        except Exception:
            logger.exception("Azure SQL DB connection unavailable.")
            self._conn = None
            raise

    def is_suppressed(
        self,
        campaign_id: str,
        ban: str,
        suppression_window_days: int,
    ) -> tuple[bool, Optional[str]]:
        """Return whether the BAN was contacted recently for this campaign."""
        suppression_start_utc = datetime.now(UTC) - timedelta(
            days=suppression_window_days
        )

        cursor = self._get_conn().cursor()
        row = cursor.execute(
            """
            SELECT TOP (1) ReasonCode
            FROM dbo.AccountContactHistory
            WHERE CampaignId = ?
              AND Ban = ?
              AND Status = 'CONTACTED'
              AND ContactDate >= ?
            ORDER BY ContactDate DESC;
            """,
            campaign_id,
            ban,
            suppression_start_utc,
        ).fetchone()

        if row is None:
            return False, None

        return True, row.ReasonCode or "RECENT_CAMPAIGN_CONTACT"

    def record_contact(
        self,
        campaign_id: str,
        ban: str,
        channel_type: str,
        transaction_id: Optional[str],
        status: str
    ) -> None:
        
        """Record a successful channel handoff without storing contact data."""
        self._insert_history(
            campaign_id=campaign_id,
            ban=ban,
            channel_type=channel_type,
            status=status,
            reason_code=None,
            transaction_id=transaction_id,
        )

    def record_outcome(
        self,
        campaign_id: str,
        ban: str,
        channel_type: str,
        status: str,
        reason_code: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> None:
        
        """Record SUPPRESSED, EXCLUDED, FAILED, or CONTACTED outcomes."""
        allowed_statuses = {"CONTACTED", "SUPPRESSED", "EXCLUDED", "FAILED"}
        if status not in allowed_statuses:
            raise ValueError(f"Unsupported status: {status}")

        self._insert_history(
            campaign_id,
            ban,
            channel_type,
            status,
            reason_code,
            transaction_id,
        )

    def _insert_history(
        self,
        campaign_id: str,
        ban: str,
        channel_type: str,
        status: str,
        reason_code: Optional[str],
        transaction_id: Optional[str],
    ) -> None:
        channel_type = channel_type.upper()
        if channel_type not in {"EMAIL", "SMS"}:
            raise ValueError(f"Unsupported channel type: {channel_type}")

        now = datetime.now(UTC)
        self._get_conn().cursor().execute(
            """
            INSERT INTO dbo.AccountContactHistory
            (
                CampaignId,
                Ban,
                ChannelType,
                Status,
                ReasonCode,
                TransactionId,
                ContactDate,
                CreatedDate
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            campaign_id,
            ban,
            channel_type,
            status,
            reason_code,
            transaction_id,
            now,
            now,
        )


@lru_cache(maxsize=1)
def get_sql_repository() -> SqlRepository:
    """Return the process-lifetime Azure SQL repository singleton."""
    return SqlRepository()
