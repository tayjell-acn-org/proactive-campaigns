"""
Suppression Service (TDD Section 5.1.x Step 3, Section 3.2 Audience Builder).

Applies account-level and contact-level suppression checks — recent contact
history, duplicate prevention, exclusion reasons, and campaign-specific
suppression windows — against the AccountEligibilitySuppression store.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from shared_packages.base_db import get_sql_repository
from shared_packages.observability import get_logger

logger = get_logger(__name__)


@dataclass
class SuppressionResult:
    suppressed: bool = False
    reason: Optional[str] = None


class SuppressionService:
    def __init__(self) -> None:
        self._repo = get_sql_repository()

    def check(self, campaign_id: str, ban: str) -> SuppressionResult:
        """
        Return whether the account is currently suppressed for this campaign.

        MVP rule: suppress if within the campaign's suppression window based on
        last-contacted history. Extend with duplicate/exclusion checks as the
        AccountEligibilitySuppression rules are finalized.
        """
        suppressed, reason = self._repo.is_suppressed(campaign_id, ban)
        if suppressed:
            logger.info(
                "Suppressed campaign=%s ban=%s reason=%s", campaign_id, ban, reason
            )
        return SuppressionResult(suppressed=suppressed, reason=reason)

    def add_contact(
        self,
        campaign_id: str,
        ban: str,
        channel_type: str,
        contact_value: str,
        transaction_id: str,
    ):
        """
        Return whether the account is currently suppressed for this campaign.

        MVP rule: suppress if within the campaign's suppression window based on
        last-contacted history. Extend with duplicate/exclusion checks as the
        AccountEligibilitySuppression rules are finalized.
        """
        self._repo.record_contact(
            campaign_id, ban, channel_type, contact_value, transaction_id
        )

        logger.info(
            "Contact added to DB campaign=%s ban=%s",
            campaign_id,
            ban,
        )
