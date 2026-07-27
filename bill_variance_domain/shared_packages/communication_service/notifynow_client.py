"""
NotifyNow REST/JSON delivery client.

NotifyNow is the approved external communication service for Business-side
AT&T proactive outreach (TDD Sections 1.2, 3.3, 7.1). Handles auth, payload
submission, bounded retries with backoff (TDD Section 9.1), and returns a
handoff result for reconciliation.
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

    def send(self, payload: dict[str, Any], idempotency_key: str = "") -> dict[str, Any]:
        """
        Submit a single campaign payload to NotifyNow with bounded retries
        (TDD Sections 9, 11.2 duplicate-send prevention).
        """
        import requests  # imported lazily

        url = f"{self.base_url}/v1/notifications"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout_seconds)
                if resp.status_code < 300:
                    logger.info("NotifyNow accepted idempotency_key=%s", idempotency_key)
                    return {"handoff_status": "HANDED_OFF", "http_status": resp.status_code,
                            "response": _safe_json(resp)}
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    raise NotifyNowError(f"Non-retryable NotifyNow error {resp.status_code}: {resp.text}")
                last_error = NotifyNowError(f"Retryable NotifyNow error {resp.status_code}: {resp.text}")
            except NotifyNowError:
                raise
            except Exception as exc:  # transient network/timeout
                last_error = exc

            if attempt < self.max_retries:
                sleep_for = self.backoff_seconds * attempt
                logger.warning("NotifyNow attempt %s/%s failed, retrying in %.1fs: %s",
                               attempt, self.max_retries, sleep_for, last_error)
                time.sleep(sleep_for)

        raise NotifyNowError(f"NotifyNow handoff failed after {self.max_retries} attempts: {last_error}")


def _safe_json(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text
