"""
Pending Credits MVP rules (TDD Section 5.1.1).

Processing goal: identify Small Business Mobility accounts with trade-in
related pending credit activity that has not started / not yet appeared as
expected, build a validated audience record, and hand off the NotifyNow
payload.

The step functions below map directly to Implementation Steps 1-10 in the
TDD. Each is a placeholder that should be wired to the approved source
systems (ECDW/Telegence credit + bill cycle tables, Customer Graph, IDM)
once access is onboarded.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from shared_packages.campaign_models import (
    AudienceRecord,
    CampaignWorkMessage,
    RecordStatus,
)
from shared_packages.communication_service import NotifyNowClient, NotifyNowError
from shared_packages.configuration import get_config_loader
from shared_packages.observability import get_logger
from shared_packages.validation import validate_email, validate_required_fields

logger = get_logger(__name__)

CAMPAIGN_ID = "PENDING_CREDITS"


def process(work: CampaignWorkMessage) -> None:
    """Entry point invoked by the processor trigger for one account."""
    ban = work.ban
    logger.info("Pending Credits: processing BAN=%s (run_id=%s)", ban, work.run_id)

    record = AudienceRecord(run_id=work.run_id, campaign_id=CAMPAIGN_ID, ban=ban)

    # Step 1: identify active/future credit activity ----------------------
    credit = _get_credit_activity(ban)
    if not credit:
        _exclude(record, "NO_CREDIT_ACTIVITY")
        return

    # Step 2: determine next-bill application status ----------------------
    bill_context = _get_next_bill_status(ban)

    # Step 3: apply pending-credit eligibility conditions -----------------
    if not _is_pending_credit_eligible(credit, bill_context):
        _exclude(record, "CREDIT_NOT_PENDING")
        return

    # Step 4: confirm Small Business Mobility segment ---------------------
    account = _lookup_account_segment(ban)
    if not account or account.get("segment") != "SMB_MOBILITY":
        _exclude(record, "OUT_OF_SEGMENT")
        return

    # Step 6: determine contact role --------------------------------------
    contact_role = _determine_contact_role(ban)
    if not contact_role:
        _exclude(record, "NO_ELIGIBLE_CONTACT_ROLE")
        return

    # Step 7: resolve contact information (Customer Graph) ----------------
    contact = _resolve_contact_info(contact_role.get("customer_id", ""))
    validation = validate_required_fields(contact, ["email"])
    if not validation.is_valid or not validate_email(contact.get("email")):
        _exclude(record, "MISSING_OR_INVALID_CONTACT")
        return

    # Step 8: determine online registration status (IDM) ------------------
    registration = _get_registration_status(ban)

    # Step 9: persist contact data for future outreach --------------------
    _persist_contact(ban, contact, contact_role)

    # Build audience record + NotifyNow payload (Step 10) -----------------
    record.customer_id = account.get("customer_id", "")
    record.eligibility_status = RecordStatus.ELIGIBLE
    record.payload = _build_notifynow_payload(
        work=work,
        account=account,
        credit=credit,
        contact=contact,
        registration=registration,
    )

    # Step 10: send outreach through NotifyNow ----------------------------
    _send_to_notifynow(record)


# --------------------------------------------------------------------------- #
# Step implementations (STUBS - wire to approved sources)
# --------------------------------------------------------------------------- #
def _get_credit_activity(ban: str) -> Optional[dict[str, Any]]:
    """Step 1: query ECDW/Telegence credit source for active/future credits."""
    # TODO: SnowflakeClient().query(<credit SQL>, {"ban": ban})
    return None


def _get_next_bill_status(ban: str) -> dict[str, Any]:
    """Step 2: query ECDW bill cycle source for next-bill application status."""
    # TODO: implement against approved bill cycle tables.
    return {}


def _is_pending_credit_eligible(credit: dict[str, Any], bill_context: dict[str, Any]) -> bool:
    """
    Step 3: pending credit exists, has not started, and credit_start_date >
    current bill cycle date. Supports existing/new account and trade-in scenarios.
    """
    # TODO: implement approved MVP eligibility rules.
    return False


def _lookup_account_segment(ban: str) -> Optional[dict[str, Any]]:
    """Step 4: confirm Small Business Mobility segment; exclude out-of-segment."""
    # TODO: implement segment lookup.
    return None


def _determine_contact_role(ban: str) -> Optional[dict[str, Any]]:
    """
    Step 6: retrieve contact list/roles and select first eligible role
    (Telecom Manager, AOP, Billing Contact, Authorized User).
    """
    # TODO: implement role selection logic.
    return None


def _resolve_contact_info(customer_id: str) -> dict[str, Any]:
    """Step 7: Customer Graph lookup for email/phone."""
    # TODO: implement Customer Graph resolution.
    return {}


def _get_registration_status(ban: str) -> dict[str, Any]:
    """Step 8: att.com Business Portal / IDM registration status."""
    # TODO: implement registration lookup.
    return {}


def _persist_contact(ban: str, contact: dict[str, Any], role: dict[str, Any]) -> None:
    """Step 9: persist to Contact Hub / approved contact repository."""
    # TODO: implement persistence.
    logger.debug("Persist contact for BAN=%s (stub)", ban)


def _build_notifynow_payload(
    work: CampaignWorkMessage,
    account: dict[str, Any],
    credit: dict[str, Any],
    contact: dict[str, Any],
    registration: dict[str, Any],
) -> dict[str, Any]:
    """Build the NotifyNow handoff payload (TDD Section 5.1.1.2)."""
    credit_amount = float(credit.get("credit_amount", 0.0) or 0.0)
    return {
        "run_id": work.run_id,
        "campaign_id": CAMPAIGN_ID,
        "idempotency_key": work.idempotency_key,
        "customer_id": account.get("customer_id", ""),
        "ban": work.ban,
        "fan": account.get("fan", ""),
        "account_type": account.get("account_type", "SMB_MOBILITY"),
        "contact_email": contact.get("email", ""),
        "contact_phone": contact.get("phone", ""),
        "preferred_language": contact.get("preferred_language", "EN"),
        "credit_amount": credit_amount,
        "credit_reference_id": credit.get("credit_reference_id", ""),
        "eligibility_status": "ELIGIBLE",
        "registration_status": registration.get("status", ""),
        "personalization_fields": {
            "credit_amount_display": f"${credit_amount:,.2f}",
        },
    }


def _send_to_notifynow(record: AudienceRecord) -> None:
    """Step 10: submit to NotifyNow and track handoff status."""
    config = get_config_loader()
    base_url = config.get_setting("NOTIFYNOW_BASE_URL")
    api_key = config.get_secret("NOTIFYNOW_API_KEY")

    if not base_url or not api_key:
        logger.warning("NotifyNow not configured; skipping send (stub mode).")
        return

    client = NotifyNowClient(base_url=base_url, api_key=api_key)
    try:
        result = client.send(record.payload)
        record.eligibility_status = RecordStatus.HANDED_OFF
        logger.info("NotifyNow handoff OK for BAN=%s: %s", record.ban, result.get("handoff_status"))
    except NotifyNowError:
        record.eligibility_status = RecordStatus.HANDOFF_FAILED
        logger.exception("NotifyNow handoff failed for BAN=%s", record.ban)
        raise  # re-raise so Service Bus retries / dead-letters the message


def _exclude(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.exclusion_reason = reason
    logger.info("Pending Credits: BAN=%s EXCLUDED (%s)", record.ban, reason)
    # TODO: persist excluded record for reconciliation.
