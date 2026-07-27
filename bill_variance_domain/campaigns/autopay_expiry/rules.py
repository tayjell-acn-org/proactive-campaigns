"""
Autopay Discount Expiry MVP rules (TDD Section 5.1.3).

Detect accounts where autopay is still active but at risk of lapsing
(expiring card, ACH issue, payment failure, enrollment issue) and prompt the
customer to update the payment method before the discount is lost.

Step mapping (TDD 5.1.3.1) — same 8-step pattern:
  Step 1  get_candidates()  Eligible Accounts Query by Segment — Snowflake   [GATHER]
  Step 2  process()         Business Rules Evaluation                        [PROCESSOR]
  Step 3                     Suppression Logic
  Step 4                     Online Account Lookup — IDM / Customer Graph
  Step 5                     Billing Contact Lookup — mBiz / ROME
  Step 6                     Customer Contacts Lookup — Customer Graph
  Step 7                     Create and Send Payload to NotifyNow
  Step 8                     Store run/eligibility/suppression — Azure SQL DB
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
from shared_packages.suppression import SuppressionService
from shared_packages.validation import validate_email, validate_required_fields

logger = get_logger(__name__)

CAMPAIGN_ID = "AUTOPAY_DISCOUNT_EXPIRY"


# Step 1 (GATHER) ------------------------------------------------------------ #
def get_candidates(config: CampaignConfig) -> list[dict[str, Any]]:
    """
    Query the Snowflake autopay/payment-method table for records loaded within
    the past day where the payment method, autopay enrollment, or discount
    eligibility has a future expiration/risk date in the approved segment.

    TODO: SnowflakeClient().query(<segment-filtered autopay-risk SQL>).
    """
    logger.warning("Using STUB candidate accounts for %s (Snowflake not wired yet).", CAMPAIGN_ID)
    return [{"ban": "000000003", "account_type": "SMB_MOBILITY"}]


# Steps 2-8 (PROCESSOR) ------------------------------------------------------ #
def process(work: CampaignWorkMessage) -> None:
    ban = work.ban
    logger.info("Autopay Expiry: processing BAN=%s (run_id=%s)", ban, work.run_id)

    record = AudienceRecord(run_id=work.run_id, campaign_id=CAMPAIGN_ID, ban=ban)
    config = get_config_loader().get_campaign("bill_variance_domain", CAMPAIGN_ID)

    # Step 2: Business Rules Evaluation
    risk = _get_autopay_risk(ban, work.source_context)
    if not risk or not _passes_business_rules(risk):
        _finalize_excluded(record, "AUTOPAY_NOT_AT_RISK")
        return

    # Step 3: Suppression Logic
    suppression = SuppressionService().check(CAMPAIGN_ID, ban)
    if suppression.suppressed:
        _finalize_suppressed(record, suppression.reason or "SUPPRESSED")
        return

    # Step 4: Online Account Lookup — IDM / Customer Graph
    online_account = _online_account_lookup(ban)

    # Step 5: Billing Contact Lookup — mBiz / ROME
    billing_contact = _billing_contact_lookup(ban)
    if not billing_contact:
        _finalize_excluded(record, "NO_BILLING_CONTACT")
        return

    # Step 6: Customer Contacts Lookup — Customer Graph
    contact = _customer_contacts_lookup(billing_contact.get("customer_id", ""))
    validation = validate_required_fields(contact, ["email"])
    if not validation.is_valid or not validate_email(contact.get("email")):
        _finalize_excluded(record, "MISSING_OR_INVALID_CONTACT")
        return

    record.customer_id = billing_contact.get("customer_id", "")
    record.eligibility_status = RecordStatus.ELIGIBLE
    record.payload = _build_notifynow_payload(work, risk, online_account, contact)

    # Step 7: Create and Send Payload to NotifyNow
    _send_to_notifynow(record, work.idempotency_key)

    # Step 8: Persist — Azure SQL DB
    get_sql_repository().upsert_eligibility(record)
    if record.handoff_status == HandoffStatus.HANDED_OFF and config:
        get_sql_repository().record_handoff(CAMPAIGN_ID, ban, work.run_id, config.suppression_window_days)


# Step implementations (STUBS) ---------------------------------------------- #
def _get_autopay_risk(ban: str, source_context: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Step 2 input: autopay-risk detail (expiring method, failed payment, etc.)."""
    return source_context.get("autopay_risk") if source_context else None  # TODO


def _passes_business_rules(risk: dict[str, Any]) -> bool:
    """Step 2: autopay active but at risk, discount impact, timing, payment-update CTA path."""
    return False  # TODO


def _online_account_lookup(ban: str) -> dict[str, Any]:
    return {}  # TODO (Step 4)


def _billing_contact_lookup(ban: str) -> Optional[dict[str, Any]]:
    return None  # TODO (Step 5)


def _customer_contacts_lookup(customer_id: str) -> dict[str, Any]:
    return {}  # TODO (Step 6)


def _build_notifynow_payload(work, risk, online_account, contact) -> dict[str, Any]:
    """Step 7: NotifyNow payload (TDD Section 5.1.3.2)."""
    discount_amount = float(risk.get("discount_amount", 0.0) or 0.0)
    return {
        "event": {
            "recipientData": [{
                "header": {
                    "source": "BOBPM",
                    "scenarioName": "BOBPM_AutopayDiscountExpiry",
                    "templateId": "BOBPM_AutopayDiscountExpiry",
                    "transactionId": work.idempotency_key,
                },
                "notificationOption": [{"moc": "email"}],
                "emaildata": {
                    "subject": "",
                    "message": "",
                    "address": {
                        "to": [{"name": contact.get("name", ""), "address": contact.get("email", "")}],
                        "from": {"name": "AT&T Offer Eligibility", "address": "cbuseb@cbus.att-mail.com"},
                        "replyTo": {"address": "cbuseb@cbus.att-mail.com"},
                    },
                },
            }],
            "attribData": [
                {"name": "BANName", "value": risk.get("ban_name", "")},
                {"name": "BANNumber", "value": work.ban},
                {"name": "nextBillCycleStartDate", "value": risk.get("next_bill_cycle_start_date", "")},
                {"name": "discountAmt", "value": f"${discount_amount:,.2f}"},
                {"name": "autopayRiskReason", "value": risk.get("risk_reason", "")},
            ],
        }
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
    logger.info("Autopay Expiry: BAN=%s EXCLUDED (%s)", record.ban, reason)
    get_sql_repository().upsert_eligibility(record)


def _finalize_suppressed(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.suppression_reason = reason
    record.handoff_status = HandoffStatus.SUPPRESSED
    logger.info("Autopay Expiry: BAN=%s SUPPRESSED (%s)", record.ban, reason)
    get_sql_repository().upsert_eligibility(record)
