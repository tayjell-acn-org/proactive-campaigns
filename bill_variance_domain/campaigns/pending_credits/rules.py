"""
Pending Credits MVP rules (TDD Section 5.1.1).

Trade-in related pending credits for Small Business Mobility accounts.

Step mapping (TDD 5.1.1.1):
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

CAMPAIGN_ID = "PENDING_CREDITS"


# --------------------------------------------------------------------------- #
# Step 1 (GATHER): Eligible Accounts Query by Segment — Snowflake
# --------------------------------------------------------------------------- #
def get_candidates(config: CampaignConfig) -> list[dict[str, Any]]:
    """
    Query the Snowflake credits/adjustments table for new credit records loaded
    within the past day with a future effective date in the approved segment.

    TODO: SnowflakeClient().query(<segment-filtered credit SQL>).
    Returns a stub so the pipeline runs before source access is onboarded.
    """
    logger.warning("Using STUB candidate accounts for %s (Snowflake not wired yet).", CAMPAIGN_ID)
    return [{"ban": "000000001", "account_type": "SMB_MOBILITY", "source_context": {"credit": {"ban_name":"hello_ban", "credit_amount" : "225"}}}]


# --------------------------------------------------------------------------- #
# Steps 2-8 (PROCESSOR): one account per invocation
# --------------------------------------------------------------------------- #
def process(work: CampaignWorkMessage) -> None:
    ban = work.ban
    logger.info("Pending Credits: processing BAN=%s (run_id=%s)", ban, work.run_id)

    record = AudienceRecord(run_id=work.run_id, campaign_id=CAMPAIGN_ID, ban=ban)
    config = get_config_loader().get_campaign("bill_variance_domain", CAMPAIGN_ID)

    # Step 2: Business Rules Evaluation --------------------------------------
    credit = _get_credit_activity(ban, work.source_context)
    if not credit or not _passes_business_rules(credit):
        _finalize_excluded(record, "CREDIT_NOT_PENDING")
        return

    # Step 3: Suppression Logic ----------------------------------------------
    suppression = SuppressionService().check(CAMPAIGN_ID, ban)
    if suppression.suppressed:
        _finalize_suppressed(record, suppression.reason or "SUPPRESSED")
        return

    # Step 4: Online Account Lookup — IDM / Customer Graph -------------------
    online_account = _online_account_lookup(ban)

    # Step 5: Billing Contact Lookup — mBiz / ROME ---------------------------
    billing_contact = _billing_contact_lookup(ban)
    if not billing_contact:
        _finalize_excluded(record, "NO_BILLING_CONTACT")
        return

    # Step 6: Customer Contacts Lookup — Customer Graph ----------------------
    contact = _customer_contacts_lookup(billing_contact.get("customer_id", ""))
    validation = validate_required_fields(contact, ["email"])
    if not validation.is_valid or not validate_email(contact.get("email")):
        _finalize_excluded(record, "MISSING_OR_INVALID_CONTACT")
        return

    # Build the eligible record + NotifyNow payload --------------------------
    record.customer_id = billing_contact.get("customer_id", "")
    record.fan = credit.get("fan", "")
    record.eligibility_status = RecordStatus.ELIGIBLE
    record.payload = _build_notifynow_payload(work, credit, online_account, contact)

    # Step 7: Create and Send Payload to NotifyNow ---------------------------
    _send_to_notifynow(record, work.idempotency_key, config)

    # Step 8: Persist run/eligibility/suppression — Azure SQL DB --------------
    get_sql_repository().upsert_eligibility(record)
    if record.handoff_status == HandoffStatus.HANDED_OFF and config:
        get_sql_repository().record_handoff(
            CAMPAIGN_ID, ban, work.run_id, config.suppression_window_days
        )


# --------------------------------------------------------------------------- #
# Step implementations (STUBS - wire to approved sources)
# --------------------------------------------------------------------------- #
def _get_credit_activity(ban: str, source_context: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Step 2 input: pending credit detail (from gather context or re-query)."""
    return source_context.get("credit") if source_context else None  # TODO


def _passes_business_rules(credit: dict[str, Any]) -> bool:
    """Step 2: credit exists, has not started, expected after current bill cycle."""
    return True  # TODO: implement approved MVP eligibility rules.


def _online_account_lookup(ban: str) -> dict[str, Any]:
    """Step 4: IDM / Customer Graph registration + CTA context."""
    return {}  # TODO


def _billing_contact_lookup(ban: str) -> Optional[dict[str, Any]]:
    """Step 5: mBiz / ROME billing contact + account relationship."""
    return {"customer_id": "000000001"}  # TODO


def _customer_contacts_lookup(customer_id: str) -> dict[str, Any]:
    """Step 6: Customer Graph email/phone/contactability/preferred method."""
    return {"email" :  "Taylor@example.com"}  # TODO


def _build_notifynow_payload(
    work: CampaignWorkMessage,
    credit: dict[str, Any],
    online_account: dict[str, Any],
    contact: dict[str, Any],
) -> dict[str, Any]:
    """Step 7: build NotifyNow event payload (TDD Section 5.1.1.2)."""
    credit_amount = float(credit.get("credit_amount", 0.0) or 0.0)
    return {
        "event": {
            "recipientData": [{
                "header": {
                    "source": "BOBPM",
                    "scenarioName": "BOBPM_PendingCredits",
                    "templateId": "BOBPM_PendingCredits",
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
                {"name": "BANName", "value": credit.get("ban_name", "")},
                {"name": "BANNumber", "value": work.ban},
                {"name": "nextBillCycleStartDate", "value": credit.get("next_bill_cycle_start_date", "")},
                {"name": "promoCreditAmt", "value": f"${credit_amount:,.2f}"},
                {"name": "promoName", "value": credit.get("promo_name", "")},
            ],
        }
    }


def _send_to_notifynow(record: AudienceRecord, idempotency_key: str, config) -> None:
    """Step 7: submit to NotifyNow and track handoff status."""
    loader = get_config_loader()
    base_url = loader.get_setting("NOTIFYNOW_BASE_URL")
    api_key = loader.get_secret("NOTIFYNOW_API_KEY")

    if not base_url or not api_key:
        logger.warning("NotifyNow not configured; skipping send (stub mode).")
        record.handoff_status = HandoffStatus.PENDING
        return

    client = NotifyNowClient(base_url=base_url, api_key=api_key)
    try:
        client.send(record.payload, idempotency_key=idempotency_key)
        record.eligibility_status = RecordStatus.HANDED_OFF
        record.handoff_status = HandoffStatus.HANDED_OFF
        logger.info("NotifyNow handoff OK for BAN=%s", record.ban)
    except NotifyNowError as exc:
        record.eligibility_status = RecordStatus.HANDOFF_FAILED
        record.handoff_status = HandoffStatus.FAILED
        record.handoff_error_code = type(exc).__name__
        logger.exception("NotifyNow handoff failed for BAN=%s", record.ban)
        get_sql_repository().upsert_eligibility(record)  # persist failure before re-raise
        raise  # re-raise so Service Bus retries / dead-letters the message


def _finalize_excluded(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.exclusion_reason = reason
    logger.info("Pending Credits: BAN=%s EXCLUDED (%s)", record.ban, reason)
    get_sql_repository().upsert_eligibility(record)


def _finalize_suppressed(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.suppression_reason = reason
    record.handoff_status = HandoffStatus.SUPPRESSED
    logger.info("Pending Credits: BAN=%s SUPPRESSED (%s)", record.ban, reason)
    get_sql_repository().upsert_eligibility(record)
