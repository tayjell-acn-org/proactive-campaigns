"""
NotifyNow REST/JSON delivery client.

NotifyNow is the approved external communication service for Business-side
"""
from __future__ import annotations

import logging
from typing import Any, Optional
import requests

logger = logging.getLogger(__name__)


class NotifyNowError(Exception):
    """Raised when a NotifyNow handoff fails."""


class NotifyNowClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def send(
        self,
        payload: dict[str, Any],
        idempotency_key: str = "",
    ) -> dict[str, Any]:
        """
        Submit a single campaign payload to NotifyNow
        """

        url = f"{self.base_url}/v1/notifications"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )

            if resp.status_code < 300:
                logger.info(
                    "NotifyNow accepted idempotency_key=%s",
                    idempotency_key,
                )
                return {
                    "handoff_status": "HANDED_OFF",
                    "http_status": resp.status_code,
                    "response": _safe_json(resp),
                }

            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                raise NotifyNowError(
                    f"Non-retryable NotifyNow error {resp.status_code}: {resp.text}"
                )

            raise NotifyNowError(
                f"NotifyNow error {resp.status_code}: {resp.text}"
            )

        except NotifyNowError:
            raise

        except Exception as exc:
            raise NotifyNowError(
                f"NotifyNow handoff failed: {exc}"
            ) from exc


def _safe_json(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text