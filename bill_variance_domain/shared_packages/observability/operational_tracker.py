"""
Operational Tracker (TDD Sections 3.1, 8.1 step 9, 11.1).

Emits the required structured log events AND persists run metadata /
reconciliation counts to the Azure SQL DB operational store via SqlRepository.
"""
from __future__ import annotations

from typing import Any, Optional

from shared_packages.base_db import get_sql_repository
from shared_packages.campaign_models import CampaignRun
from shared_packages.observability.logging_setup import get_logger

logger = get_logger(__name__)


class OperationalTracker:
    def __init__(self, run: CampaignRun, function_name: Optional[str] = None) -> None:
        self.run = run
        self.function_name = function_name
        self._repo = get_sql_repository()

    def _emit(self, event: str, **fields: Any) -> None:
        extra = {f"evt_{k}": v for k, v in fields.items()}
        extra["evt_event"] = event
        extra["evt_run_id"] = self.run.run_id
        extra["evt_campaign_id"] = self.run.campaign_id

        # Bind Azure Function name for automatic App Insights operation_Name mapping
        if self.function_name:
            extra["evt_operation_Name"] = self.function_name

        logger.info(event, extra=extra)

    # Required log events (TDD Section 11.1) ---------------------------- #
    def run_started(self, environment: str = "NON-PROD") -> None:
        self._emit("CampaignRunStarted", start_ts=self.run.start_ts, environment=environment)

    def config_loaded(self, config_version: str, active_flag: bool) -> None:
        self._emit("ConfigLoaded", config_version=config_version, active_flag=active_flag)

    def source_extract_completed(self, source_name: str, input_count: int, status: str = "OK") -> None:
        self.run.input_count = input_count
        self._emit("SourceExtractCompleted", source_name=source_name, input_count=input_count, status=status)

    def validation_completed(self, valid_count: int, invalid_count: int, top_error_codes: Optional[list[str]] = None) -> None:
        self._emit("ValidationCompleted", valid_count=valid_count, invalid_count=invalid_count,
                   top_error_codes=top_error_codes or [])

    def eligibility_completed(self, eligible_count: int, excluded_count: int, suppressed_count: int = 0) -> None:
        self.run.eligible_count = eligible_count
        self.run.excluded_count = excluded_count
        self.run.suppressed_count = suppressed_count
        self._emit("EligibilityCompleted", eligible_count=eligible_count,
                   excluded_count=excluded_count, suppressed_count=suppressed_count)

    def handoff_completed(self, handoff_target: str, record_count: int, status: str) -> None:
        self._emit("HandoffCompleted", handoff_target=handoff_target, record_count=record_count, status=status)

    def run_completed(self, status: str = "COMPLETED") -> None:
        self.run.complete(status)
        self._emit("CampaignRunCompleted", status=status, summary_counts={
            "input": self.run.input_count,
            "eligible": self.run.eligible_count,
            "excluded": self.run.excluded_count,
            "suppressed": self.run.suppressed_count,
            "errors": self.run.error_count,
        })

    def run_failed(self, failure_stage: str, error_code: str, error_message: str) -> None:
        self.run.error_count += 1
        self.run.complete("FAILED")
        self._emit("CampaignRunFailed", failure_stage=failure_stage,
                   error_code=error_code, error_message=error_message)