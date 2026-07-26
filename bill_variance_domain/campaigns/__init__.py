"""
Campaign factory / mapping used by processor_trigger.py.

Register each campaign's entry point here. Adding a new Bill Variance
campaign is a config + rules-module change, not a structural platform change
(TDD Sections 4, 14).
"""
from __future__ import annotations

from typing import Callable, Optional

from shared_packages.campaign_models import CampaignWorkMessage

from .pending_credits.rules import process as process_pending_credits
from .promotion_expiry.rules import process as process_promotion_expiry
from .autopay_expiry.rules import process as process_autopay_expiry
from .international_roaming_charges.rules import process as process_international_roaming

# campaign_id -> handler(work: CampaignWorkMessage) -> None
_CAMPAIGN_HANDLERS: dict[str, Callable[[CampaignWorkMessage], None]] = {
    "PENDING_CREDITS": process_pending_credits,
    "PROMOTION_EXPIRY": process_promotion_expiry,
    "AUTOPAY_DISCOUNT_EXPIRY": process_autopay_expiry,
    "INTERNATIONAL_ROAMING_CHARGES": process_international_roaming,
}


def get_campaign_handler(campaign_id: str) -> Optional[Callable[[CampaignWorkMessage], None]]:
    return _CAMPAIGN_HANDLERS.get(campaign_id)
