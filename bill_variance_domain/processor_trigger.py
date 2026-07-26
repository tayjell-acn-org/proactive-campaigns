"""
Bill Variance processor trigger (Service Bus).

Consumes one work message at a time and dispatches to the campaign-specific
rules module via the campaign factory. Scales out on queue depth; a single
message failure fails only that message (retry -> DLQ), not the whole run
(TDD Sections 8.1, 8.2, 9).
"""
from __future__ import annotations

import azure.functions as func

from campaigns import get_campaign_handler
from shared_packages.campaign_models import CampaignWorkMessage
from shared_packages.observability import get_logger

logger = get_logger(__name__)
bp = func.Blueprint()


@bp.service_bus_queue_trigger(
    arg_name="message",
    queue_name="%SERVICE_BUS_QUEUE_NAME%",
    connection="SERVICE_BUS_CONNECTION",
)
def process_bill_variance(message: func.ServiceBusMessage) -> None:
    raw = message.get_body().decode("utf-8")
    work = CampaignWorkMessage.from_json(raw)

    logger.info(
        "Processing campaign=%s ban=%s run_id=%s attempt=%s",
        work.campaign_id, work.ban, work.run_id, message.delivery_count,
    )

    handler = get_campaign_handler(work.campaign_id)
    if handler is None:
        # Unsupported campaign: log and let the message complete so it does not
        # loop forever. Consider routing to DLQ explicitly if preferred.
        logger.warning("No handler registered for campaign %s", work.campaign_id)
        return

    # Any exception raised here abandons the message, so Service Bus retries
    # and eventually dead-letters it after max delivery count is exceeded.
    handler(work)
