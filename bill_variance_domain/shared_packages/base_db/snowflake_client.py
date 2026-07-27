"""
Snowflake source client (TDD Section 3.3 - Snowflake enterprise data access).

Isolates query/connection logic from the campaign rules engine so source
systems can be swapped or mocked (TDD Section 3.2 - Source Extract Layer).
Used by the gather side for the "Eligible Accounts Query by Segment" step.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SnowflakeClient:
    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = None,
        warehouse: Optional[str] = None,
        role: Optional[str] = None,
    ) -> None:
        self.account = account or os.getenv("SNOWFLAKE_ACCOUNT")
        self.user = user or os.getenv("SNOWFLAKE_USER")
        self.password = password or os.getenv("SNOWFLAKE_PASSWORD")
        self.database = database or os.getenv("SNOWFLAKE_DATABASE")
        self.schema = schema or os.getenv("SNOWFLAKE_SCHEMA")
        self.warehouse = warehouse or os.getenv("SNOWFLAKE_WAREHOUSE")
        self.role = role or os.getenv("SNOWFLAKE_ROLE")
        self._conn = None

    def connect(self):
        if self._conn is None:
            import snowflake.connector  # imported lazily

            self._conn = snowflake.connector.connect(
                account=self.account,
                user=self.user,
                password=self.password,
                database=self.database,
                schema=self.schema,
                warehouse=self.warehouse,
                role=self.role,
            )
            logger.info("Opened Snowflake connection to %s", self.account)
        return self._conn

    def query(self, sql: str, params: Optional[dict[str, Any]] = None) -> list[dict[str, Any]]:
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params or {})
            columns = [c[0] for c in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "SnowflakeClient":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()
