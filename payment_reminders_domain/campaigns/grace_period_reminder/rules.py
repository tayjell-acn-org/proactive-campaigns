"""
Grace Period Reminder rules (SCAFFOLD).

Implement mirroring bill_variance_domain/campaigns/pending_credits/rules.py:
get_candidates(config) for Step 1, then process(work) for the remaining steps.
"""
from __future__ import annotations

from typing import Any

from shared_packages.campaign_models import CampaignConfig, CampaignWorkMessage
from shared_packages.observability import get_logger

logger = get_logger(__name__)

CAMPAIGN_ID = "GRACE_PERIOD_REMINDER"


def get_candidates(config: CampaignConfig) -> list[dict[str, Any]]:
    return []  # TODO


def process(work: CampaignWorkMessage) -> None:
    logger.info("Grace Period Reminder - scaffold, not yet implemented.")
    raise NotImplementedError
