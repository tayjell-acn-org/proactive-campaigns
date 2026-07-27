"""Campaign factory for the Payment Reminders domain (SCAFFOLD)."""
from typing import Callable, Optional

_CAMPAIGN_MODULES: dict[str, object] = {}


def get_candidate_provider(campaign_id: str) -> Optional[Callable]:
    module = _CAMPAIGN_MODULES.get(campaign_id)
    return getattr(module, "get_candidates", None) if module else None


def get_campaign_handler(campaign_id: str) -> Optional[Callable]:
    module = _CAMPAIGN_MODULES.get(campaign_id)
    return getattr(module, "process", None) if module else None
