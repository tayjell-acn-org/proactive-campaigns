"""
Operational Tracker.

Captures run metadata, record counts, errors, and handoff status required
for supportability, reconciliation, and governance (TDD Sections 3.1, 8.1,
11.1). This reference implementation logs structured events; swap the
_persist() body for the approved operational store when confirmed.
"""
from __future__ import annotations

from typing import Any, Optional

from shared_packages.campaign_models import CampaignRun
from shared_packages.observability.logging_setup import get_logger

logger = get_logger(__name__)


class OperationalTracker:
    def __init__(self, run: CampaignRun) -> None:
        self.run = run

    def _persist(self, event: str, **fields: Any) -> None:
        # TODO: persist to approved operational store (table/App Insights).
        extra = {f"evt_{k}": v for k, v in fields.items()}
        extra["evt_event"] = event
        extra["evt_run_id"] = self.run.run_id
        extra["evt_campaign_id"] = self.run.campaign_id
        logger.info(event, extra=extra)

    # Required log events (TDD Section 11.1) ---------------------------- #
    def run_started(self, environment: str = "NON-PROD") -> None:
        self._persist("CampaignRunStarted", start_ts=self.run.start_ts, environment=environment)

    def config_loaded(self, config_version: str, active_flag: bool) -> None:
        self._persist("ConfigLoaded", config_version=config_version, active_flag=active_flag)

    def source_extract_completed(self, source_name: str, input_count: int, status: str = "OK") -> None:
        self.run.input_count = input_count
        self._persist("SourceExtractCompleted", source_name=source_name, input_count=input_count, status=status)

    def validation_completed(self, valid_count: int, invalid_count: int, top_error_codes: Optional[list[str]] = None) -> None:
        self._persist("ValidationCompleted", valid_count=valid_count, invalid_count=invalid_count, top_error_codes=top_error_codes or [])

    def eligibility_completed(self, eligible_count: int, excluded_count: int) -> None:
        self.run.eligible_count = eligible_count
        self.run.excluded_count = excluded_count
        self._persist("EligibilityCompleted", eligible_count=eligible_count, excluded_count=excluded_count)

    def handoff_completed(self, handoff_target: str, record_count: int, status: str) -> None:
        self._persist("HandoffCompleted", handoff_target=handoff_target, record_count=record_count, status=status)

    def run_completed(self, status: str = "COMPLETED") -> None:
        self.run.complete(status)
        self._persist("CampaignRunCompleted", status=status, total_counts={
            "input": self.run.input_count,
            "eligible": self.run.eligible_count,
            "excluded": self.run.excluded_count,
            "errors": self.run.error_count,
        })

    def run_failed(self, failure_stage: str, error_code: str, error_message: str) -> None:
        self.run.error_count += 1
        self.run.complete("FAILED")
        self._persist("CampaignRunFailed", failure_stage=failure_stage, error_code=error_code, error_message=error_message)
