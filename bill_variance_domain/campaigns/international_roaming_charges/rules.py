"""
International Roaming Charges MVP rules (TDD Section 5.1.4).

Objective: reduce bill shock when international roaming activity or travel
package provisioning is detected (IDP for land roaming, CDP for cruise).
Reassure coverage, explain expected charges, and provide opt-out/remove
where approved.

Step functions map to Implementation Steps 1-9 in the TDD.
"""
from __future__ import annotations

from typing import Any, Optional

from shared_packages.campaign_models import AudienceRecord, CampaignWorkMessage, RecordStatus
from shared_packages.observability import get_logger

logger = get_logger(__name__)

CAMPAIGN_ID = "INTERNATIONAL_ROAMING_CHARGES"


def process(work: CampaignWorkMessage) -> None:
    logger.info("Intl Roaming: processing BAN=%s (run_id=%s)", work.ban, work.run_id)
    record = AudienceRecord(run_id=work.run_id, campaign_id=CAMPAIGN_ID, ban=work.ban)

    # Step 1: detect roaming or package event
    event = _detect_roaming_event(work.ban)
    if not event:
        _exclude(record, "NO_ROAMING_EVENT")
        return

    # Step 2: confirm package coverage and charge context
    # Step 3: apply roaming eligibility conditions
    # Step 4: lookup account information and segment
    # Step 5: determine contact role
    # Step 6: resolve contact information
    # Step 7: determine online registration status
    # Step 8: persist contact and campaign context
    # Step 9: send outreach through NotifyNow
    raise NotImplementedError("Intl Roaming Steps 2-9 not yet implemented.")


def _detect_roaming_event(ban: str) -> Optional[dict[str, Any]]:
    """Step 1: identify qualifying roaming/cruise events or IDP/CDP provisioning."""
    return None  # TODO


def _exclude(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.exclusion_reason = reason
    logger.info("Intl Roaming: BAN=%s EXCLUDED (%s)", record.ban, reason)
