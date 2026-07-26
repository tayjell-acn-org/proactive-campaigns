"""
Promotion Expiry MVP rules (TDD Section 5.1.2).

Objective: notify customers when a promotional discount / bill credit / rate
benefit is approaching expiration or has ended, explain expected bill impact,
and route to a static self-service page or approved CTA.

Step functions map to Implementation Steps 1-9 in the TDD. Wire each to the
approved sources before activation.
"""
from __future__ import annotations

from typing import Any, Optional

from shared_packages.campaign_models import AudienceRecord, CampaignWorkMessage, RecordStatus
from shared_packages.observability import get_logger

logger = get_logger(__name__)

CAMPAIGN_ID = "PROMOTION_EXPIRY"


def process(work: CampaignWorkMessage) -> None:
    logger.info("Promotion Expiry: processing BAN=%s (run_id=%s)", work.ban, work.run_id)
    record = AudienceRecord(run_id=work.run_id, campaign_id=CAMPAIGN_ID, ban=work.ban)

    # Step 1: identify promotion expiry population
    promotion = _get_expiring_promotion(work.ban)
    if not promotion:
        _exclude(record, "NO_EXPIRING_PROMOTION")
        return

    # Step 2: determine bill impact and timing
    impact = _calculate_bill_impact(promotion)

    # Step 3: apply promotion eligibility conditions
    if not _is_eligible(promotion, impact):
        _exclude(record, "NOT_ELIGIBLE")
        return

    # Step 4: lookup account information and segment
    # Step 5: determine contact role
    # Step 6: resolve contact information
    # Step 7: determine online registration status
    # Step 8: persist contact and campaign context
    # Step 9: send outreach through NotifyNow
    raise NotImplementedError("Promotion Expiry Steps 4-9 not yet implemented.")


def _get_expiring_promotion(ban: str) -> Optional[dict[str, Any]]:
    """Step 1: query source for promotions/credits ending soon or recently ended."""
    return None  # TODO


def _calculate_bill_impact(promotion: dict[str, Any]) -> dict[str, Any]:
    """Step 2: compare discount value, end date, billing cycle, next bill timing."""
    return {}  # TODO


def _is_eligible(promotion: dict[str, Any], impact: dict[str, Any]) -> bool:
    """Step 3: include active accounts with expiring/ended promo + approved CTA path."""
    return False  # TODO


def _exclude(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.exclusion_reason = reason
    logger.info("Promotion Expiry: BAN=%s EXCLUDED (%s)", record.ban, reason)
