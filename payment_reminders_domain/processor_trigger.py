"""Payment Reminders processor trigger (Service Bus) - SCAFFOLD.

Copy the pattern from bill_variance_domain/processor_trigger.py.
"""
from __future__ import annotations

import azure.functions as func

from shared_packages.observability import get_logger

logger = get_logger(__name__)
bp = func.Blueprint()


@bp.service_bus_queue_trigger(arg_name="message", queue_name="%SERVICE_BUS_QUEUE_NAME%",
                              connection="SERVICE_BUS_CONNECTION")
def process_payment_reminders(message: func.ServiceBusMessage) -> None:
    logger.info("Payment Reminders processor - scaffold, not yet implemented.")
    # TODO: implement mirroring bill_variance_domain/processor_trigger.py
