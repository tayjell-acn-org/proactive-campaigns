"""
NotifyNow REST/JSON delivery client.

NotifyNow is the approved external communication service for Business-side
AT&T proactive outreach (TDD Section 1.2 / 5.1.1 Step 10). This adapter
handles auth, payload submission, bounded retries with backoff, and
returns a handoff result for reconciliation.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NotifyNowError(Exception):
    """Raised when a NotifyNow handoff fails after retries."""


class NotifyNowClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Submit a single campaign payload to NotifyNow.

        Uses bounded retries with backoff for transient errors (TDD Section 9.1).
        Returns a dict describing the handoff result for the Operational Tracker.
        """
        import requests  # imported lazily

        url = f"{self.base_url}/v1/notifications"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Prevent duplicate sends on retry (TDD Section 11.2 alert condition).
            "Idempotency-Key": payload.get("idempotency_key")
            or payload.get("run_id", ""),
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(
                    url, json=payload, headers=headers, timeout=self.timeout_seconds
                )
                if resp.status_code < 300:
                    logger.info(
                        "NotifyNow accepted run_id=%s campaign=%s",
                        payload.get("run_id"),
                        payload.get("campaign_id"),
                    )
                    return {
                        "handoff_status": "HANDED_OFF",
                        "http_status": resp.status_code,
                        "response": _safe_json(resp),
                    }

                # 4xx (except 429) are non-retryable.
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    raise NotifyNowError(
                        f"Non-retryable NotifyNow error {resp.status_code}: {resp.text}"
                    )

                last_error = NotifyNowError(
                    f"Retryable NotifyNow error {resp.status_code}: {resp.text}"
                )
            except NotifyNowError:
                raise
            except Exception as exc:  # transient network/timeout
                last_error = exc

            if attempt < self.max_retries:
                sleep_for = self.backoff_seconds * attempt
                logger.warning(
                    "NotifyNow attempt %s/%s failed, retrying in %.1fs: %s",
                    attempt, self.max_retries, sleep_for, last_error,
                )
                time.sleep(sleep_for)

        raise NotifyNowError(
            f"NotifyNow handoff failed after {self.max_retries} attempts: {last_error}"
        )


def _safe_json(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text
