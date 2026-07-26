"""
Autopay Discount Expiry MVP rules (TDD Section 5.1.3).

Objective: detect early risk where autopay is still active but at risk of
lapsing (expiring card, ACH issue, payment failure, enrollment issue) and
prompt the customer to update the payment method before the discount is lost.

Step functions map to Implementation Steps 1-9 in the TDD.
"""
from __future__ import annotations

from typing import Any, Optional

from shared_packages.campaign_models import AudienceRecord, CampaignWorkMessage, RecordStatus
from shared_packages.observability import get_logger

logger = get_logger(__name__)

CAMPAIGN_ID = "AUTOPAY_DISCOUNT_EXPIRY"


def process(work: CampaignWorkMessage) -> None:
    logger.info("Autopay Expiry: processing BAN=%s (run_id=%s)", work.ban, work.run_id)
    record = AudienceRecord(run_id=work.run_id, campaign_id=CAMPAIGN_ID, ban=work.ban)

    # Step 1: identify autopay risk signals
    risk = _get_autopay_risk(work.ban)
    if not risk:
        _exclude(record, "NO_AUTOPAY_RISK")
        return

    # Step 2: determine discount impact and timing
    # Step 3: apply autopay eligibility conditions
    # Step 4: lookup account information and segment
    # Step 5: determine contact role
    # Step 6: resolve contact information
    # Step 7: determine online registration status
    # Step 8: persist contact and campaign context
    # Step 9: send outreach through NotifyNow
    raise NotImplementedError("Autopay Expiry Steps 2-9 not yet implemented.")


def _get_autopay_risk(ban: str) -> Optional[dict[str, Any]]:
    """Step 1: identify active autopay accounts with early risk signals."""
    return None  # TODO


def _exclude(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.exclusion_reason = reason
    logger.info("Autopay Expiry: BAN=%s EXCLUDED (%s)", record.ban, reason)
