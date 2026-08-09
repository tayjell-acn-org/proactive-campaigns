"""
Bill Variance gather triggers (Timer).

Each campaign runs on its OWN schedule, so there is one timer function per
campaign, each bound to its own app setting (e.g. %PENDING_CREDITS_SCHEDULE%).
All share the _run_gather() logic and publish to the same Service Bus queue,
tagged with campaign_id. The single shared processor consumes them regardless
of when they were published.

Per-campaign Step 1 (Eligible Accounts Query by Segment — Snowflake, or the
roaming event detection for Intl Roaming) lives in each campaign's rules module
and is resolved via the campaign factory (TDD Sections 3, 5.1, 8.1).
"""
from __future__ import annotations

import os

import azure.functions as func

from campaigns import get_candidate_provider
from shared_packages.campaign_models import CampaignConfig, CampaignRun, CampaignWorkMessage
from shared_packages.configuration import get_config_loader
from shared_packages.observability import OperationalTracker, get_logger

logger = get_logger(__name__)
bp = func.Blueprint()

DOMAIN = "bill_variance_domain"
SERVICE_BUS_CONNECTION = "SERVICE_BUS_CONNECTION"
QUEUE_NAME_SETTING = "SERVICE_BUS_QUEUE_NAME"


# --------------------------------------------------------------------------- #
# One timer function per campaign — each has its own schedule app setting.
# NCRONTAB: {second} {minute} {hour} {day} {month} {day-of-week}
# --------------------------------------------------------------------------- #
@bp.timer_trigger(
    schedule="%PENDING_CREDITS_SCHEDULE%",              # e.g. "0 0 8 * * *"
    arg_name="timer", run_on_startup=False, use_monitor=True,
)
def gather_pending_credits(timer: func.TimerRequest, context: func.Context) -> None:
    _run_gather("PENDING_CREDITS", context)


@bp.timer_trigger(
    schedule="%PROMOTION_EXPIRY_SCHEDULE%",             # e.g. "0 30 8 * * *"
    arg_name="timer", run_on_startup=False, use_monitor=True,
)
def gather_promotion_expiry(timer: func.TimerRequest, context: func.Context) -> None:
    _run_gather("PROMOTION_EXPIRY", context)


# --------------------------------------------------------------------------- #
# Shared gather-and-publish logic (campaign-agnostic).
# --------------------------------------------------------------------------- #
def _run_gather(campaign_id: str, context: func.Context) -> None:
    config_loader = get_config_loader()
    queue_name = config_loader.get_setting(QUEUE_NAME_SETTING, "bill-variance-work")

    campaign = config_loader.get_campaign(DOMAIN, campaign_id)
    if campaign is None or not campaign.active_flag:
        logger.info("Campaign %s is not active; skipping gather.", campaign_id)
        return

    run = CampaignRun(campaign_id=campaign.campaign_id)
    tracker = OperationalTracker(run=run, function_name = context.function_name)
    tracker.run_started()
    tracker.config_loaded(campaign.output_schema_version, campaign.active_flag)

    try:
        candidates = _get_candidates(campaign)
        tracker.source_extract_completed(campaign.source_profile, len(candidates))

        published = _publish_work_messages(
            run=run, campaign_id=campaign.campaign_id, candidates=candidates,
            connection_setting=SERVICE_BUS_CONNECTION, queue_name=queue_name,
        )
        logger.info("Published %s work messages for %s (run_id=%s)",
                    published, campaign.campaign_id, run.run_id)
        tracker.run_completed("PUBLISHED")

    except Exception as exc:  # noqa: BLE001
        logger.exception("Gather failed for %s", campaign.campaign_id)
        tracker.run_failed("GATHER", type(exc).__name__, str(exc))
        raise


def _get_candidates(campaign: CampaignConfig) -> list[dict]:
    """Step 1: delegate to the campaign's own candidate provider."""
    provider = get_candidate_provider(campaign.campaign_id)
    if provider is None:
        logger.warning("No candidate provider for %s.", campaign.campaign_id)
        return []
    return provider(campaign)


def _publish_work_messages(
    run: CampaignRun, campaign_id: str, candidates: list[dict],
    connection_setting: str, queue_name: str,
) -> int:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage

    connection_string = os.environ[connection_setting]
    count = 0

    with ServiceBusClient.from_connection_string(connection_string) as sb_client:
        with sb_client.get_queue_sender(queue_name=queue_name) as sender:
            batch = sender.create_message_batch()
            for candidate in candidates:
                work = CampaignWorkMessage(
                    run_id=run.run_id,
                    campaign_id=campaign_id,
                    domain="BILL_VARIANCE",
                    account_id=candidate.get("account_id", ""),
                    ban=candidate.get("ban", ""),
                    source_context=candidate.get("source_context", {}),
                )
                message = ServiceBusMessage(
                    work.to_json(),
                    message_id=work.idempotency_key,   # dedupe at the broker
                    correlation_id=work.correlation_id,
                )
                try:
                    batch.add_message(message)
                except ValueError:
                    sender.send_messages(batch)
                    batch = sender.create_message_batch()
                    batch.add_message(message)
                count += 1

            if len(batch):
                sender.send_messages(batch)

    return count
