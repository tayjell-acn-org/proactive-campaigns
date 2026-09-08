from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Optional
from uuid import uuid4

from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError


logger = logging.getLogger(__name__)


class CosmosRepository:
    """Azure Cosmos DB (NoSQL API) repository for campaign contact history.

    Notes
    -----
    * The container partition key is ``/banHash``, so the stored documents
      and all partition lookups must use ``banHash``.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        key: Optional[str] = None,
        database_name: Optional[str] = None,
        container_name: Optional[str] = None,
    ) -> None:
        self.endpoint = endpoint or os.getenv("COSMOS_ENDPOINT")
        self.key = key or os.getenv("COSMOS_KEY")
        self.database_name = database_name or os.getenv(
            "COSMOS_DATABASE_NAME",
            "proactive",
        )
        self.container_name = container_name or os.getenv(
            "COSMOS_CONTAINER_NAME",
            "account-contact-history",
        )

        self._client: Optional[CosmosClient] = None
        self._container = None

    def _get_container(self):
        if not self.endpoint:
            raise RuntimeError("COSMOS_ENDPOINT is not configured.")

        if not self.key:
            raise RuntimeError("COSMOS_KEY is not configured.")

        try:
            if self._container is None:
                self._client = CosmosClient(
                    url=self.endpoint,
                    credential=self.key,
                )

                database = self._client.get_database_client(
                    self.database_name
                )

                self._container = database.get_container_client(
                    self.container_name
                )

                # Verify that the container exists and is accessible.
                self._container.read()

                logger.info(
                    "Opened Cosmos DB container connection: %s/%s",
                    self.database_name,
                    self.container_name,
                )

            return self._container

        except Exception:
            logger.exception("Cosmos DB connection unavailable.")
            self._client = None
            self._container = None
            raise

    def is_suppressed(
        self,
        campaign_id: str,
        ban: str,
        suppression_window_days: int,
    ) -> tuple[bool, Optional[str]]:
        """Return whether the BAN was contacted recently for this campaign."""

        suppression_start = (
            datetime.now(UTC) - timedelta(days=suppression_window_days)
        ).isoformat()

        query = """
        SELECT TOP 1
            c.reasonCode,
            c.contactDate
        FROM c
        WHERE c.campaignId = @campaignId
          AND c.status = "CONTACTED"
          AND c.contactDate >= @suppressionStart
        ORDER BY c.contactDate DESC
        """

        parameters = [
            {"name": "@campaignId", "value": campaign_id},
            {"name": "@suppressionStart", "value": suppression_start},
        ]

        try:
            # ban is passed as the partition key value, which limits the
            # query to a single logical partition.
            results = self._get_container().query_items(
                query=query,
                parameters=parameters,
                partition_key=ban,
            )

            row = next(iter(results), None)

            if row is None:
                return False, None

            return (
                True,
                row.get("reasonCode") or "RECENT_CAMPAIGN_CONTACT",
            )

        except CosmosHttpResponseError:
            logger.exception(
                "Cosmos DB suppression query failed for campaign %s.",
                campaign_id,
            )
            raise

    def record_contact(
        self,
        campaign_id: str,
        ban: str,
        channel_type: str,
        transaction_id: Optional[str],
        status: str = "CONTACTED",
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

        status = status.upper()

        if status not in allowed_statuses:
            raise ValueError(f"Unsupported status: {status}")

        self._insert_history(
            campaign_id=campaign_id,
            ban=ban,
            channel_type=channel_type,
            status=status,
            reason_code=reason_code,
            transaction_id=transaction_id,
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
        status = status.upper()

        if channel_type not in {"EMAIL", "SMS"}:
            raise ValueError(f"Unsupported channel type: {channel_type}")

        now = datetime.now(UTC).isoformat()

        document = {
            # Each history event needs a unique Cosmos document ID.
            "id": str(uuid4()),
            # Must exactly match the /banHash partition key casing.
            "banHash": ban,
            "campaignId": campaign_id,
            "channelType": channel_type,
            "status": status,
            "reasonCode": reason_code,
            "transactionId": transaction_id,
            "contactDate": now,
            "createdDate": now,
        }

        try:
            self._get_container().create_item(body=document)

            logger.info(
                "Recorded Cosmos DB outcome for campaign %s with status %s.",
                campaign_id,
                status,
            )

        except CosmosHttpResponseError:
            logger.exception(
                "Failed to record Cosmos DB outcome for campaign %s.",
                campaign_id,
            )
            raise


@lru_cache(maxsize=1)
def get_cosmos_repository() -> CosmosRepository:
    """Return the process-lifetime Cosmos repository singleton."""

    return CosmosRepository()
