"""Payment Reminders gather trigger (Timer) - SCAFFOLD.

Copy the per-campaign timer pattern from bill_variance_domain/gatherer_trigger.py.
"""
from __future__ import annotations

import azure.functions as func

from shared_packages.observability import get_logger

logger = get_logger(__name__)
bp = func.Blueprint()

DOMAIN = "payment_reminders_domain"


@bp.timer_trigger(schedule="%GRACE_PERIOD_REMINDER_SCHEDULE%", arg_name="timer",
                  run_on_startup=False, use_monitor=True)
def gather_grace_period_reminder(timer: func.TimerRequest) -> None:
    logger.info("Payment Reminders gather - scaffold, not yet implemented.")
    # TODO: implement mirroring bill_variance_domain/gatherer_trigger.py
