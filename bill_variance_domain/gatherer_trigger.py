"""
Bill Variance gather trigger (Timer).

Responsibilities (TDD Sections 3, 8.1, 8.2):
  1. Start a campaign run for each active Bill Variance campaign.
  2. Load domain/campaign config.
  3. Retrieve the eligible source population (Snowflake/ECDW/Telegence).
  4. Publish ONE Service Bus message per candidate account/work item so the
     processor can scale out, retry, and throttle independently.

The timer cadence is a placeholder; the approved run window/frequency should
be finalized and driven from configuration.
"""
from __future__ import annotations

import json

import azure.functions as func

from shared_packages.campaign_models import CampaignRun, CampaignWorkMessage
from shared_packages.configuration import get_config_loader
from shared_packages.observability import OperationalTracker, get_logger


logger = get_logger(__name__)
bp = func.Blueprint()

DOMAIN = "bill_variance_domain"
SERVICE_BUS_CONNECTION = "SERVICE_BUS_CONNECTION"
QUEUE_NAME_SETTING = "SERVICE_BUS_QUEUE_NAME"


@bp.timer_trigger(
    schedule="%GATHER_SCHEDULE%",   # e.g. "0 0 8 * * *" (08:00 UTC daily)
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def gather_bill_variance(timer: func.TimerRequest) -> None:
    config = get_config_loader()
    queue_name = config.get_setting(QUEUE_NAME_SETTING, "bill-variance-work")

    active_campaigns = config.get_active_campaigns(DOMAIN)
    if not active_campaigns:
        logger.info("No active Bill Variance campaigns; nothing to gather.")
        return

    for campaign in active_campaigns:
        run = CampaignRun(campaign_id=campaign.campaign_id)
        tracker = OperationalTracker(run)
        tracker.run_started()
        tracker.config_loaded(campaign.output_schema_version, campaign.active_flag)

        try:
            candidate_accounts = _get_candidate_accounts(campaign.campaign_id, config)
            tracker.source_extract_completed(campaign.source_profile, len(candidate_accounts))

            published = _publish_work_messages(
                run=run,
                campaign_id=campaign.campaign_id,
                accounts=candidate_accounts,
                connection_setting=SERVICE_BUS_CONNECTION,
                queue_name=queue_name,
            )

            logger.info(
                "Published %s work messages for %s (run_id=%s)",
                published, campaign.campaign_id, run.run_id,
            )
            tracker.run_completed("PUBLISHED")

        except Exception as exc:  # noqa: BLE001
            logger.exception("Gather failed for %s", campaign.campaign_id)
            tracker.run_failed("GATHER", type(exc).__name__, str(exc))
            raise


def _get_candidate_accounts(campaign_id: str, config) -> list[dict]:
    """
    Retrieve candidate accounts for the campaign.

    TODO: Implement per-campaign source adapters/queries against the approved
    source (e.g. ECDW credit + bill cycle tables for Pending Credits,
    TDD Section 5.1.1 Steps 1-3). Returning a stub keeps the pipeline runnable
    end-to-end before source access is onboarded.
    """
    logger.warning("Using STUB candidate accounts for %s (no source wired yet).", campaign_id)
    return [
        {"ban": "000000001", "account_type": "SMB_MOBILITY"},
    ]


def _publish_work_messages(
    run: CampaignRun,
    campaign_id: str,
    accounts: list[dict],
    connection_setting: str,
    queue_name: str,
) -> int:
    import os
    from azure.servicebus import ServiceBusClient, ServiceBusMessage

    connection_string = os.environ[connection_setting]
    count = 0

    with ServiceBusClient.from_connection_string(connection_string) as sb_client:
        with sb_client.get_queue_sender(queue_name=queue_name) as sender:
            batch = sender.create_message_batch()
            for account in accounts:
                work = CampaignWorkMessage(
                    run_id=run.run_id,
                    campaign_id=campaign_id,
                    domain="BILL_VARIANCE",
                    account_id=account.get("account_id", ""),
                    ban=account.get("ban", ""),
                )
                message = ServiceBusMessage(
                    work.to_json(),
                    message_id=work.idempotency_key,      # dedupe at the broker
                    correlation_id=work.correlation_id,
                )
                try:
                    batch.add_message(message)
                except ValueError:
                    # Batch full: send and start a new one.
                    sender.send_messages(batch)
                    batch = sender.create_message_batch()
                    batch.add_message(message)
                count += 1

            if len(batch):
                sender.send_messages(batch)

    return count
