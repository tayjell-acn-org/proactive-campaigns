"""
Campaign factory / mapping used by the gather and processor triggers.

Each campaign module exposes two functions:
  - get_candidates(config) -> list[dict]   # Step 1 (gather side: Snowflake/event query)
  - process(work)          -> None         # Steps 2-8/9 (processor side)

Adding a new Bill Variance campaign is a config + rules-module change plus one
line here — not a structural platform change (TDD Sections 4, 14).
"""
from __future__ import annotations

from typing import Callable, Optional

from shared_packages.campaign_models import CampaignConfig, CampaignWorkMessage

from .pending_credits import rules as pending_credits
from .promotion_expiry import rules as promotion_expiry
from .autopay_expiry import rules as autopay_expiry
from .international_roaming_charges import rules as international_roaming

_CAMPAIGN_MODULES = {
    "PENDING_CREDITS": pending_credits,
    "PROMOTION_EXPIRY": promotion_expiry,
    "AUTOPAY_DISCOUNT_EXPIRY": autopay_expiry,
    "INTERNATIONAL_ROAMING_CHARGES": international_roaming,
}


def get_candidate_provider(campaign_id: str) -> Optional[Callable[[CampaignConfig], list[dict]]]:
    module = _CAMPAIGN_MODULES.get(campaign_id)
    return getattr(module, "get_candidates", None) if module else None


def get_campaign_handler(campaign_id: str) -> Optional[Callable[[CampaignWorkMessage], None]]:
    module = _CAMPAIGN_MODULES.get(campaign_id)
    return getattr(module, "process", None) if module else None
