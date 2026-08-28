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
import os
import uuid

from shared_packages.campaign_models.models import CampaignRun
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
DOMAIN = "bill_variance_domain"
SERVICE_BUS_CONNECTION = "SERVICE_BUS_CONNECTION"
QUEUE_NAME_SETTING = "SERVICE_BUS_QUEUE_NAME"
BATCH_SIZE = 500


# --------------------------------------------------------------------------- #
# Step 1 (GATHER): Eligible Accounts Query by Segment — Snowflake
# ---------------------------------------------------------------------------

def get_candidates(run: CampaignRun, campaign_config: CampaignConfig, queue_name: str) -> int:
    """
    Retrieve pending credit records and publish them to Service Bus.

    Future implementation:
      - Query Snowflake using a cursor.
      - Use fetchmany() rather than fetchall().
      - Publish batches directly to Service Bus to keep memory usage low.

    Current implementation:
      - Uses local stub data until Snowflake onboarding is complete.
      - Sends stub records through the same Service Bus publishing path.
    """

    total_published = 0

    try:
        #
        # TODO: Snowflake implementation
        #
        # sql = """
        # SELECT
        #     p.srv_accs_id,
        #     p.actvt_amt        AS pending_credit_amount,
        #     p.actvt_eff_dt     AS effective_date,
        #     p.actvt_add_dt     AS added_date,
        #     p.load_dt_tm       AS load_date,
        #     p.updt_dt_tm       AS update_date,
        #     s.bl_cyc_id        AS bill_cycle_id,
        #     a.acct_nbr         AS ban,
        #     s.acct_id,
        #     c.bl_cyc_clos_day  AS bill_close_day
        # FROM ...
        # """
        #
        # with SnowflakeClient().cursor() as cursor:
        #     cursor.execute(sql)
        #
        #     while rows := cursor.fetchmany(BATCH_SIZE):
        #
        #         candidates = [
        #             {
        #                 "srvAccsId": row["SRV_ACCS_ID"],
        #                 "pendingCreditAmount": float(row["PENDING_CREDIT_AMOUNT"]),
        #                 "effectiveDate": str(row["EFFECTIVE_DATE"]),
        #                 "addedDate": str(row["ADDED_DATE"]),
        #                 "loadDate": row["LOAD_DATE"].isoformat(),
        #                 "updateDate": row["UPDATE_DATE"].isoformat(),
        #                 "billCycleId": row["BILL_CYCLE_ID"],
        #                 "ban": str(row["BAN"]),
        #                 "accountId": row["ACCT_ID"],
        #                 "billCloseDay": row["BILL_CLOSE_DAY"]
        #             }
        #             for row in rows
        #         ]
        #
        #         published = _publish_work_messages(
        #             run=run,
        #             campaign_id=campaign_config.campaign_id,
        #             candidates=candidates,
        #             connection_setting=SERVICE_BUS_CONNECTION,
        #             queue_name=queue_name,
        #         )
        #
        #         total_published += published
        #
        # return total_published

        raise NotImplementedError("Snowflake source not yet onboarded")

    except Exception:
        logger.warning(
            "Using STUB pending credit records for %s (Snowflake not wired yet).",
            campaign_config.campaign_id,
        )

        candidates = [
            {
                "BAN": "298541763218",
                "ACCT_ID": "1527846391",
                "SRV_ACCS_ID": "1745628391",
                "PHONE_NUMBER": "4045552718",
                "CURR_FAN_ID": "71234567",
                "PLATFORM_HANDLER": "MyATT",
                "PROMO_ID": "1688459012",
                "CURRENT_CREDIT_COUNT": "1",
                "CREDIT_AMOUNT": "25.00",
                "EFFECTIVE_DATE": "2026-08-25",
                "ADDED_DATE": "2026-08-18",
                "LOAD_DATE": "2026-08-19 04:15:22.000",
                "UPDATE_DATE": "2026-08-26 05:00:54.000",
                "BILL_CYCLE_ID": "62415",
                "BILL_CLOSE_DAY": "18",
                "CG_EMAIL": "sarah.jenkins@yahoo.com",
                "CG_FIRST_NM": "SARAH",
                "CG_PHONE_NBR": "4045552718",
                "CG_PROFILE_SLID": "sarah.jenkins@yahoo.com",
                "CG_FN_IND": "false"
            },
            {
                "BAN": "301847562990",
                "ACCT_ID": "1673928450",
                "SRV_ACCS_ID": "1827465903",
                "PHONE_NUMBER": "3125559841",
                "CURR_FAN_ID": "74567821",
                "PLATFORM_HANDLER": "MyATT",
                "PROMO_ID": "1723567845",
                "CURRENT_CREDIT_COUNT": "1",
                "CREDIT_AMOUNT": "30.56",
                "EFFECTIVE_DATE": "2026-08-25",
                "ADDED_DATE": "2026-08-07",
                "LOAD_DATE": "2026-08-08 05:04:11.000",
                "UPDATE_DATE": "2026-08-26 05:00:54.000",
                "BILL_CYCLE_ID": "62415",
                "BILL_CLOSE_DAY": "18",
                "CG_EMAIL": "michael.turner@gmail.com",
                "CG_FIRST_NM": "MICHAEL",
                "CG_PHONE_NBR": "3125559841",
                "CG_PROFILE_SLID": "michael.turner@gmail.com",
                "CG_FN_IND": "false"
            }
        ]

        for i in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[i:i + BATCH_SIZE]

            published = _publish_work_messages(
                run=run,
                campaign_id=campaign_config.campaign_id,
                candidates=batch,
                connection_setting=SERVICE_BUS_CONNECTION,
                queue_name=queue_name,
            )

            total_published += published

            logger.info(
                "Published %s work messages for %s (run_id=%s)",
                published,
                campaign_config.campaign_id,
                run.run_id,
            )

    return total_published


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

    transaction_id = work.idempotency_key or str(uuid.uuid4())

    recipient_email = contact.get("email") or contact.get("Email") or contact.get("cg_email")
    recipient_name = (
        contact.get("first_name") or contact.get("name") or contact.get("CG_FIRST_NM") or ""
    )

    ban_last4 = work.ban[-4:] if work.ban else ""

    customer_first_name = recipient_name or ""
    customer_platform = (
        credit.get("platform") or credit.get("PLATFORM_HANDLER") or work.source_context.get("platform") if work.source_context else None
    ) or "MyATT"

    # build credits list
    credits_list: list[dict[str, Any]] = []
    incoming_credits = credit.get("credits") if isinstance(credit.get("credits"), list) else None
    if incoming_credits:
        for idx, c in enumerate(incoming_credits[:3], start=1):
            credit_type = c.get("creditType") or c.get("credit_type") or "Pending"
            credit_name = c.get("creditName") or c.get("credit_name") or credit_type
            credits_list.append({
                "sequence": idx,
                "creditType": credit_type,
                "creditName": credit_name,
                "creditAmount": float(c.get("creditAmount", c.get("credit_amount", 0.0)) or 0.0),
                "lineLast4": c.get("lineLast4", c.get("line_last4", "")),
                "postingDate": c.get("postingDate", c.get("posting_date", "")),
            })
    else:
        # derive a single credit for now (static/temporary)
        credits_list.append({
            "sequence": 1,
            "creditType": credit.get("credit_type", "Trade In"),
            "creditName": credit.get("credit_name", credit.get("credit_type", "Trade In")),
            "creditAmount": credit_amount,
            "lineLast4": credit.get("line_last4", "5678"),
            "postingDate": credit.get("posting_date", "10-2026"),
        })

    # request id for tracking
    request_id = f"{transaction_id}-req-{uuid.uuid4()}"

    phone_sources = [
        contact.get("CG_PHONE_NBR"),
        (work.source_context.get("PHONE_NUMBER") if work.source_context else None),
    ]
    phone = next((p for p in phone_sources if p), None)

    phone_number = phone if isinstance(phone, str) and phone.strip() else ""

    # decide whether to build SMS or Email payload
    preferred_moc = None
    try:
        preferred_moc = work.source_context.get("moc") if work.source_context else None
    except Exception:
        preferred_moc = None

    want_sms = False
    if preferred_moc == "sms":
        want_sms = True
    elif (not recipient_email) and phone_number:
        want_sms = True

    if want_sms:
        payload = {
            "event": {
                "recipientData": [
                    {
                        "header": {
                            "source": "PO",
                            "templateId": "PO_Cr_SMS",
                            "scenarioName": "PendingCredits",
                            "transactionId": transaction_id,
                        },
                        "notificationOption": [{"moc": "sms"}],
                        "smsData": {
                            "details": {
                                "contactData": {
                                    "phoneNumber": {"number": phone_number},
                                    "sysId": "PO",
                                    "requestId": request_id,
                                }
                            }
                        },
                    }
                ],
                "attribData": [
                    {"name": "customerFirstName", "value": customer_first_name or ""},
                    {"name": "customerPlatform", "value": customer_platform},
                    {"name": "onlineRegistered", "value": "Y"},
                    {"name": "credits", "value": credits_list},
                ],
            }
        }
    else:
        payload = {
            "event": {
                "recipientData": [
                    {
                        "header": {
                            "source": "PO",
                            "templateId": "PO_Cr",
                            "scenarioName": "PendingCredits",
                            "transactionId": transaction_id,
                        },
                        "notificationOption": [{"moc": "email"}],
                        "emaildata": {
                            "subject": "Your promotional credit update",
                            "address": {
                                "to": [
                                    {"name": recipient_name, "address": recipient_email}
                                ],
                                "cc": [],
                                "bcc": [],
                                "from": {"name": "AT&T Proactive Outreach", "address": "cbuseb@cbus.att-mail.com"},
                                "replyTo": {"address": ""},
                            },
                        },
                    }
                ],
                "attribData": [
                    {"name": "customerFirstName", "value": customer_first_name},
                    {"name": "customerPlatform", "value": customer_platform},
                    {"name": "onlineRegistered", "value": "Y"},
                    {"name": "banLast4", "value": ban_last4},
                    {"name": "credits", "value": credits_list},
                ],
            }
        }

    # debug output
    print("NotifyNow payload:")
    print(payload)
    logger.debug("NotifyNow payload built: %s", payload)

    return payload


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


def _publish_work_messages(
    run: CampaignRun, campaign_id: str, candidates: list[dict],
    connection_setting: str, queue_name: str,
) -> int:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage

    connection_string = os.environ[connection_setting]
    count = 0

    print("SB CONN NAME: " + connection_string)
    print("SB QUEUE NAME: " + queue_name)

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

                    source_context={
                        "credit": {
                            "credit_amount": float(
                                candidate.get("pendingCreditAmount",
                                              candidate.get("PENDING_CREDIT_AMOUNT",
                                                            candidate.get("CREDIT_AMOUNT", 0.0))) or 0.0
                            ),
                            "credits": candidate.get("credits") if isinstance(candidate.get("credits"), list) else None,
                            "platform": candidate.get("PLATFORM_HANDLER", candidate.get("platform")),
                            "effective_date": candidate.get("pendingCreditEffectiveDate",
                                                             candidate.get("PENDING_CREDIT_EFFECTIVE_DATE",
                                                                           candidate.get("EFFECTIVE_DATE", ""))),
                            "bill_close_day": candidate.get("billCloseDay", candidate.get("BILL_CLOSE_DAY", 0)),
                            "ban": candidate.get("ban", candidate.get("BAN", "")),
                        }
                    },
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
