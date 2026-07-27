"""
Common campaign data models.

These models are campaign-agnostic and reused by every domain Function App.
Field names/types map to TDD Section 6 (Data Design) — CampaignConfig,
CampaignRun, CampaignWorkMessage, and the AccountEligibilitySuppression
entity (represented here by AudienceRecord). Physical schemas should be
finalized against approved Azure SQL DB standards.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import json
import uuid


class RecordStatus(str, Enum):
    """Recommended record status values (TDD Section 6.2)."""

    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"
    HANDED_OFF = "HANDED_OFF"
    HANDOFF_FAILED = "HANDOFF_FAILED"


class HandoffStatus(str, Enum):
    """NotifyNow handoff outcome tracked on AccountEligibilitySuppression."""

    PENDING = "PENDING"
    HANDED_OFF = "HANDED_OFF"
    FAILED = "FAILED"
    SUPPRESSED = "SUPPRESSED"


@dataclass
class CampaignConfig:
    """Campaign-level runtime configuration (TDD Sections 4.1 / 6.1)."""

    campaign_id: str
    campaign_name: str
    active_flag: bool = False
    run_frequency: str = "DAILY"
    source_profile: str = ""
    eligibility_rule_set: str = ""
    suppression_rule_set: str = "StandardSuppressionRules"
    suppression_window_days: int = 30
    delivery_channel: str = "EMAIL"
    handoff_target: str = "NOTIFYNOW"
    output_schema_version: str = "1.0"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignConfig":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class CampaignWorkMessage:
    """
    Service Bus message emitted by the gather trigger and consumed by the
    processor trigger (TDD Section 6.1). One message == one unit of work
    (one account / campaign event) to enable scale-out and retries.
    """

    run_id: str
    campaign_id: str
    domain: str
    account_id: str = ""
    ban: str = ""
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    attempt_count: int = 0
    idempotency_key: str = ""
    # Optional per-work-item context carried from gather (e.g. Snowflake row,
    # roaming event details) so the processor doesn't re-query Step 1.
    source_context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.idempotency_key:
            self.idempotency_key = f"{self.run_id}:{self.campaign_id}:{self.ban or self.account_id}"

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "CampaignWorkMessage":
        data = json.loads(raw)
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class CampaignRun:
    """Tracks a single execution instance (TDD Section 6.1)."""

    campaign_id: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_ts: Optional[str] = None
    status: str = "STARTED"
    input_count: int = 0
    eligible_count: int = 0
    excluded_count: int = 0
    suppressed_count: int = 0
    error_count: int = 0

    def complete(self, status: str = "COMPLETED") -> None:
        self.status = status
        self.end_ts = datetime.now(timezone.utc).isoformat()


@dataclass
class AudienceRecord:
    """
    A single evaluated record and its outcome. Maps to the
    AccountEligibilitySuppression entity (TDD Section 6.1): tracks eligibility,
    exclusion, suppression, and handoff history per account/campaign.
    """

    run_id: str
    campaign_id: str
    customer_id: str = ""
    ban: str = ""
    fan: str = ""
    eligibility_status: RecordStatus = RecordStatus.INVALID
    exclusion_reason: Optional[str] = None
    suppression_reason: Optional[str] = None
    handoff_status: HandoffStatus = HandoffStatus.PENDING
    handoff_target: str = "NOTIFYNOW"
    handoff_error_code: Optional[str] = None
    payload: dict[str, Any] = field(default_factory=dict)
    updated_ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
