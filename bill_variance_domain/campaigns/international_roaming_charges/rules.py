"""
International Roaming Charges MVP rules (TDD Section 5.1.4).

Event-driven campaign to reduce bill shock when international roaming activity
or travel-package provisioning is detected (IDP land roaming, CDP cruise).
Reassure coverage, explain expected charges, provide opt-out/remove CTA.

Step mapping (TDD 5.1.4.1) — distinct 9-step event pattern:
  Step 1  get_candidates()  Detect roaming or package event                 [GATHER]
  Step 2  process()         Confirm package coverage and charge context     [PROCESSOR]
  Step 3                     Apply roaming eligibility conditions
  Step 4                     Lookup account information and segment
  Step 5                     Determine contact role
  Step 6                     Resolve contact information — Customer Graph
  Step 7                     Determine online registration status — IDM
  Step 8                     Persist contact and campaign context
  Step 9                     Send outreach through NotifyNow
"""
from __future__ import annotations

from typing import Any, Optional

from shared_packages.base_db import get_sql_repository
from shared_packages.campaign_models import (
    AudienceRecord,
    CampaignConfig,
    CampaignWorkMessage,
    HandoffStatus,
    RecordStatus,
)
from shared_packages.communication_service import NotifyNowClient, NotifyNowError
from shared_packages.configuration import get_config_loader
from shared_packages.observability import get_logger
from shared_packages.validation import validate_email, validate_required_fields

logger = get_logger(__name__)

CAMPAIGN_ID = "INTERNATIONAL_ROAMING_CHARGES"


# Step 1 (GATHER): Detect roaming or package event -------------------------- #
def get_candidates(config: CampaignConfig) -> list[dict[str, Any]]:
    """
    Source adapter / event listener for qualifying international roaming events,
    cruise network events, roaming charge signals, or IDP/CDP provisioning
    confirmation events.

    TODO: wire to the approved roaming event source. The event detail is carried
    forward in each work message's source_context so the processor doesn't
    re-detect.
    """
    logger.warning("Using STUB roaming events for %s (event source not wired yet).", CAMPAIGN_ID)
    return [{
        "ban": "000000004",
        "subscriber_id": "SUB-0004",
        "source_context": {
            "roaming_event": {
                "roaming_event_type": "LAND_ROAMING",
                "country_or_location": "",
                "package_type": "IDP",
                "package_status": "ACTIVE",
                "daily_rate": 0.00,
            }
        },
    }]


# Steps 2-9 (PROCESSOR) ------------------------------------------------------ #
def process(work: CampaignWorkMessage) -> None:
    ban = work.ban
    logger.info("Intl Roaming: processing BAN=%s (run_id=%s)", ban, work.run_id)

    record = AudienceRecord(run_id=work.run_id, campaign_id=CAMPAIGN_ID, ban=ban)
    config = get_config_loader().get_campaign("bill_variance_domain", CAMPAIGN_ID)

    event = (work.source_context or {}).get("roaming_event")
    if not event:
        _finalize_excluded(record, "NO_ROAMING_EVENT")
        return

    # Step 2: Confirm package coverage and charge context
    coverage = _confirm_coverage(event)

    # Step 3: Apply roaming eligibility conditions
    if not _is_eligible(event, coverage):
        _finalize_excluded(record, "NOT_ELIGIBLE")
        return

    # Step 4: Lookup account information and segment
    account = _lookup_account_segment(ban)
    if not account or account.get("segment") != "SMB_MOBILITY":
        _finalize_excluded(record, "OUT_OF_SEGMENT")
        return

    # Step 5: Determine contact role
    contact_role = _determine_contact_role(ban)
    if not contact_role:
        _finalize_excluded(record, "NO_ELIGIBLE_CONTACT_ROLE")
        return

    # Step 6: Resolve contact information — Customer Graph
    contact = _resolve_contact_info(contact_role.get("customer_id", ""))
    validation = validate_required_fields(contact, ["email"])
    if not validation.is_valid or not validate_email(contact.get("email")):
        _finalize_excluded(record, "MISSING_OR_INVALID_CONTACT")
        return

    # Step 7: Determine online registration status — IDM
    registration = _get_registration_status(ban)

    # Step 8: Persist contact and campaign context (pre-handoff snapshot)
    record.customer_id = account.get("customer_id", "")
    record.fan = account.get("fan", "")
    record.eligibility_status = RecordStatus.ELIGIBLE
    record.payload = _build_notifynow_payload(work, account, event, coverage, contact, registration)
    get_sql_repository().upsert_eligibility(record)

    # Step 9: Send outreach through NotifyNow
    _send_to_notifynow(record, work.idempotency_key)
    get_sql_repository().upsert_eligibility(record)
    if record.handoff_status == HandoffStatus.HANDED_OFF and config:
        get_sql_repository().record_handoff(CAMPAIGN_ID, ban, work.run_id, config.suppression_window_days)


# Step implementations (STUBS) ---------------------------------------------- #
def _confirm_coverage(event: dict[str, Any]) -> dict[str, Any]:
    """Step 2: IDP/CDP coverage, daily rate, coverage vs charge vs opt-out branch."""
    return {}  # TODO


def _is_eligible(event: dict[str, Any], coverage: dict[str, Any]) -> bool:
    """Step 3: active Business Mobility line, qualifying event, approved CTA path."""
    return False  # TODO


def _lookup_account_segment(ban: str) -> Optional[dict[str, Any]]:
    """Step 4: BAN/FAN/subscriber/hierarchy -> confirm Business Mobility."""
    return None  # TODO


def _determine_contact_role(ban: str) -> Optional[dict[str, Any]]:
    """Step 5: select account/telecom-management recipient role."""
    return None  # TODO


def _resolve_contact_info(customer_id: str) -> dict[str, Any]:
    """Step 6: Customer Graph email/phone/language/contactability."""
    return {}  # TODO


def _get_registration_status(ban: str) -> dict[str, Any]:
    """Step 7: IDM registration + coverage-details / opt-out URLs."""
    return {}  # TODO


def _build_notifynow_payload(work, account, event, coverage, contact, registration) -> dict[str, Any]:
    """Step 9 payload (TDD Section 5.1.4.2 — flat schema for roaming)."""
    daily_rate = float(event.get("daily_rate", 0.0) or 0.0)
    return {
        "run_id": work.run_id,
        "campaign_id": CAMPAIGN_ID,
        "customer_id": account.get("customer_id", ""),
        "ban": work.ban,
        "fan": account.get("fan", ""),
        "subscriber_id": account.get("subscriber_id", ""),
        "line_last_four": account.get("line_last_four", ""),
        "account_type": account.get("account_type", "SMB_MOBILITY"),
        "contact_email": contact.get("email", ""),
        "contact_phone": contact.get("phone", ""),
        "preferred_language": contact.get("preferred_language", "EN"),
        "roaming_event_type": event.get("roaming_event_type", ""),
        "country_or_location": event.get("country_or_location", ""),
        "package_type": event.get("package_type", ""),
        "package_status": event.get("package_status", ""),
        "daily_rate": daily_rate,
        "eligibility_status": "ELIGIBLE",
        "personalization_fields": {
            "daily_rate_display": f"${daily_rate:,.2f}",
            "coverage_message": coverage.get("coverage_message", ""),
            "cta_label": "View coverage details",
            "cta_url": registration.get("coverage_details_url", ""),
            "opt_out_url": registration.get("opt_out_url", ""),
        },
    }


def _send_to_notifynow(record: AudienceRecord, idempotency_key: str) -> None:
    loader = get_config_loader()
    base_url = loader.get_setting("NOTIFYNOW_BASE_URL")
    api_key = loader.get_secret("NOTIFYNOW_API_KEY")
    if not base_url or not api_key:
        logger.warning("NotifyNow not configured; skipping send (stub mode).")
        return
    client = NotifyNowClient(base_url=base_url, api_key=api_key)
    try:
        client.send(record.payload, idempotency_key=idempotency_key)
        record.eligibility_status = RecordStatus.HANDED_OFF
        record.handoff_status = HandoffStatus.HANDED_OFF
    except NotifyNowError as exc:
        record.eligibility_status = RecordStatus.HANDOFF_FAILED
        record.handoff_status = HandoffStatus.FAILED
        record.handoff_error_code = type(exc).__name__
        get_sql_repository().upsert_eligibility(record)
        raise


def _finalize_excluded(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.exclusion_reason = reason
    logger.info("Intl Roaming: BAN=%s EXCLUDED (%s)", record.ban, reason)
    get_sql_repository().upsert_eligibility(record)
