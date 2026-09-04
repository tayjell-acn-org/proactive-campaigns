"""
Pending Credits MVP rules (TDD Section 5.1.1).

Trade-in related pending credits for Small Business Mobility accounts.

Step mapping (TDD 5.1.1.1):
 Step 1  get_candidates()  Eligible Accounts Query by Segment — Snowflake   [GATHER]
 Step 2  process()         Business Rules Evaluation                        [PROCESSOR]
 Step 3                    Suppression Logic
 Step 4                    Online Account Lookup — IDM / Customer Graph
 Step 5                    Billing Contact Lookup — mBiz / ROME
 Step 6                    Customer Contacts Lookup — Customer Graph
 Step 7                    Create and Send Payload to NotifyNow
 Step 8                    Store run/eligibility/suppression — Azure SQL DB
"""

from __future__ import annotations

from typing import Any, Optional
import os
import uuid
import json

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
from shared_packages.utility.utility_functions import _publish_work_messages

logger = get_logger(__name__)

CAMPAIGN_ID = "PENDING_CREDITS"
DOMAIN = "bill_variance_domain"
SERVICE_BUS_CONNECTION = "SERVICE_BUS_CONNECTION"
QUEUE_NAME_SETTING = "SERVICE_BUS_QUEUE_NAME"
BATCH_SIZE = 500


# --------------------------------------------------------------------------- #
# Step 1 (GATHER): Eligible Accounts Query by Segment — Snowflake
# ---------------------------------------------------------------------------


def get_candidates(
    run: CampaignRun, campaign_config: CampaignConfig, queue_name: str
) -> int:
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

    from pathlib import Path

    # Resolve to bill_variance_domain then into shared_packages/test_data
    data_file = (
        Path(__file__).resolve().parents[2]
        / "shared_packages"
        / "test_data"
        / "pending_credits_test_data.json"
    )

    logger.debug(
        "Resolved pending credits test data path: %s (exists=%s)",
        str(data_file),
        data_file.exists(),
    )

    if not data_file.exists():
        logger.error("Pending credits test data not found at %s", str(data_file))
        raise FileNotFoundError(f"Pending credits test data not found: {data_file}")

    with data_file.open("r", encoding="utf-8") as file:
        candidates = json.load(file)

        # candidates = [
        #     {
        #         "BAN": "298541763218",
        #         "ACCT_ID": "1527846391",
        #         "CURR_FAN_ID": "71234567",
        #         "PLATFORM_HANDLER": "MyATT",
        #         "CURRENT_CREDIT_COUNT": "2",
        #         "BILL_CYCLE_ID": "62415",
        #         "BILL_CLOSE_DAY": "18",
        #         "CG_EMAIL": "sarah.jenkins@yahoo.com",
        #         "CG_FIRST_NM": "SARAH",
        #         "CG_PHONE_NBR": "4045552718",
        #         "CG_PROFILE_SLID": "sarah.jenkins@yahoo.com",
        #         "CG_FN_IND": "false",
        #         "CREDIT_DETAILS": [
        #             {
        #                 "PROMO_ID": "1688459012",
        #                 "PHONE_NUMBER": "4045552718",
        #                 "SRV_ACCS_ID": "1745628391",
        #                 "CREDIT_AMOUNT": "25",
        #                 "EFFECTIVE_DATE": "2026-08-25",
        #                 "ADDED_DATE": "2026-08-18",
        #             },
        #             {
        #                 "PROMO_ID": "1723567845",
        #                 "PHONE_NUMBER": "3125559841",
        #                 "SRV_ACCS_ID": "1827465903",
        #                 "CREDIT_AMOUNT": "30.56",
        #                 "EFFECTIVE_DATE": "2026-08-25",
        #                 "ADDED_DATE": "2026-08-07",
        #             },
        #         ],
        #     }
        # ]

        for i in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[i : i + BATCH_SIZE]

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
    # Get Source context from campaign message
    source_context = work.source_context

    # Step 1: Get Account level items
    acct_info = _get_acct_info(source_context)
    ban = acct_info.get("ban")

    logger.info("Pending Credits: processing BAN=%s (run_id=%s)", ban, work.run_id)
    record = AudienceRecord(run_id=work.run_id, campaign_id=CAMPAIGN_ID, ban=ban)
    config = get_config_loader().get_campaign("bill_variance_domain", CAMPAIGN_ID)

    # Step 2: Build Credits List --------------------------------------
    credit_list = _build_credit_list(source_context)

    # Step 3: Get Customer Contact Infomation  ----------------------
    contact_info = _get_customer_contact_info(source_context)

    # Step 4: Suppression Logic ----------------------------------------------
    suppression = SuppressionService().check(CAMPAIGN_ID, ban)
    if suppression.suppressed:
        SuppressionService().add_contact(
                            campaign_id=CAMPAIGN_ID,
                            ban=ban,
                            channel_type="EMAIL",
                            transaction_id=f"{work.idempotency_key}-email",
                            status="SUPPRESSED"
                        )
        SuppressionService().add_contact(
                    campaign_id=CAMPAIGN_ID,
                    ban=ban,
                    channel_type="SMS",
                    transaction_id=f"{work.idempotency_key}-sms",
                    status="SUPPRESSED"
                )
        return


    # Step 7: Create and Send Payload to NotifyNow ---------------------------

    # Send email and/or SMS depending on available contact information
    if contact_info.get("email"):
        record.payload = _build_notifynow_payload(
            work,
            credit_list,
            acct_info,
            contact_info,
            "email",
        )
        _send_to_notifynow(
            record,
            f"{work.idempotency_key}-email",
            config,
        )
        SuppressionService().add_contact(
            campaign_id=CAMPAIGN_ID,
            ban=ban,
            channel_type="EMAIL",
            transaction_id=f"{work.idempotency_key}-email",
            status="CONTACTED"
        )
    if contact_info.get("phone"):
        record.payload = _build_notifynow_payload(
            work,
            credit_list,
            acct_info,
            contact_info,
            "sms",
        )
        _send_to_notifynow(
            record,
            f"{work.idempotency_key}-sms",
            config,
        )
        SuppressionService().add_contact(
            campaign_id=CAMPAIGN_ID,
            ban=ban,
            channel_type="SMS",
            transaction_id=f"{work.idempotency_key}-sms",
            status="CONTACTED"
        )


# --------------------------------------------------------------------------- #
# Step implementations (STUBS - wire to approved sources)
# --------------------------------------------------------------------------- #


def _build_credit_list(
    source_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build NotifyNow credit list from source CREDIT_DETAILS."""

    credit_list: list[dict[str, Any]] = []

    credit_details = source_context.get("CREDIT_DETAILS", []) or []

    for sequence, credit_detail in enumerate(
        credit_details[:3],
        start=1,
    ):
        phone_number = credit_detail.get("PHONE_NUMBER", "") or ""

        credit_type = credit_detail.get("CREDIT_TYPE") or "Trade In"

        credit_name = credit_detail.get("CREDIT_NAME") or credit_type

        credit_list.append(
            {
                "sequence": sequence,
                "creditType": credit_type,
                "creditName": credit_name,
                "creditAmount": float(credit_detail.get("CREDIT_AMOUNT", 0) or 0),
                "lineLast4": (phone_number[-4:] if phone_number else ""),
                # TODO: derive posting date based on final business rule
                "postingDate": (credit_detail.get("POSTING_DATE", "") or ""),
            }
        )

    return credit_list


def _get_customer_contact_info(
    source_context: dict[str, Any],
) -> dict[str, Any]:
    """Get best available email and phone for customer."""

    contact_dict: dict[str, Any] = {}

    first_name = source_context.get("CG_FIRST_NM", "") or ""
    email = source_context.get("CG_EMAIL", "")
    phone = source_context.get("CG_PHONE_NBR", "") or ""

    profile_slid = source_context.get("CG_PROFILE_SLID", "")
    if profile_slid:
        online_registered = True
        contact_dict["online_registered"] = True
    else:
        online_registered = False
        contact_dict["online_registered"] = False

    # Always take first name even if blank
    contact_dict["first_name"] = first_name

    if email:
        contact_dict["email"] = email
    if online_registered:
        contact_dict["email"] = profile_slid

    if phone:
        contact_dict["phone"] = phone

    return contact_dict


def _get_acct_info(
    source_context: dict[str, Any],
) -> dict[str, Any]:
    acct_info_dict = {}

    ban = source_context.get("BAN", "")
    fan = source_context.get("CURR_FAN_ID", "")
    platform_handler = source_context.get("PLATFORM_HANDLER", "")

    acct_info_dict["ban"] = ban
    acct_info_dict["fan"] = fan
    acct_info_dict["platform_handler"] = platform_handler

    return acct_info_dict


def _build_notifynow_payload(
    work: CampaignWorkMessage,
    credit: list[dict[str, Any]],
    online_account: dict[str, Any],
    contact: dict[str, Any],
    moc: str,
) -> dict[str, Any]:
    """Step 7: build NotifyNow event payload (TDD Section 5.1.1.2)."""
    if moc == "email":
        return _build_email_payload(
            work,
            credit,
            online_account,
            contact,
        )
    if moc == "sms":
        return _build_sms_payload(
            work,
            credit,
            online_account,
            contact,
        )
    raise ValueError(f"Unsupported method of contact: {moc}")


def _build_email_payload(
    work: CampaignWorkMessage,
    credit: list[dict[str, Any]],
    online_account: dict[str, Any],
    contact: dict[str, Any],
) -> dict[str, Any]:
    """Build NotifyNow email payload."""

    transaction_id = (
        f"{work.idempotency_key}-email" if work.idempotency_key else str(uuid.uuid4())
    )

    recipient_email = contact.get("email", "")
    recipient_name = contact.get("first_name", "")

    ban = work.source_context.get("BAN", "") if work.source_context else ""

    customer_platform = (
        work.source_context.get("PLATFORM_HANDLER") if work.source_context else None
    ) or "MyATT"

    online_registered = "Y" if contact.get("online_registered") else "N"

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
                    "notificationOption": [
                        {
                            "moc": "email",
                        }
                    ],
                    "emaildata": {
                        "subject": "Your promotional credit update",
                        "address": {
                            "to": [
                                {
                                    "name": recipient_name,
                                    "address": recipient_email,
                                }
                            ],
                            "cc": [],
                            "bcc": [],
                            "from": {
                                "name": "AT&T Proactive Outreach",
                                "address": "cbuseb@cbus.att-mail.com",
                            },
                            "replyTo": {
                                "address": "",
                            },
                        },
                    },
                }
            ],
            "attribData": [
                {
                    "name": "customerFirstName",
                    "value": recipient_name,
                },
                {
                    "name": "customerPlatform",
                    "value": customer_platform,
                },
                {
                    "name": "onlineRegistered",
                    "value": online_registered,
                },
                {
                    "name": "banLast4",
                    "value": (ban[-4:] if ban else ""),
                },
                {
                    "name": "credits",
                    "value": credit[:3],
                },
            ],
        }
    }

    logger.debug(
        "NotifyNow email payload built: %s",
        payload,
    )

    return payload


def _build_sms_payload(
    work: CampaignWorkMessage,
    credit: list[dict[str, Any]],
    online_account: dict[str, Any],
    contact: dict[str, Any],
) -> dict[str, Any]:
    """Build NotifyNow SMS payload."""

    transaction_id = (
        f"{work.idempotency_key}-sms" if work.idempotency_key else str(uuid.uuid4())
    )

    request_id = f"{transaction_id}-req-{uuid.uuid4()}"

    phone_number = contact.get("phone", "")

    recipient_name = contact.get("first_name", "")

    ban = work.source_context.get("BAN", "") if work.source_context else ""

    customer_platform = (
        work.source_context.get("PLATFORM_HANDLER") if work.source_context else None
    ) or "MyATT"

    online_registered = "Y" if contact.get("online_registered") else "N"

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
                    "notificationOption": [
                        {
                            "moc": "sms",
                        }
                    ],
                    "smsData": {
                        "details": {
                            "contactData": {
                                "phoneNumber": {
                                    "number": phone_number,
                                },
                                "sysId": "PO",
                                "requestId": request_id,
                            }
                        }
                    },
                }
            ],
            # Following the field table, which says event.attribData.
            # Confirm against the SMS example because the example
            # appears to place attribData inside recipientData.
            "attribData": [
                {
                    "name": "customerFirstName",
                    "value": recipient_name,
                },
                {
                    "name": "customerPlatform",
                    "value": customer_platform,
                },
                {
                    "name": "onlineRegistered",
                    "value": online_registered,
                },
                {
                    "name": "banLast4",
                    "value": (ban[-4:] if ban else ""),
                },
                {
                    "name": "credits",
                    "value": credit[:3],
                },
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
        get_sql_repository().upsert_eligibility(
            record
        )  # persist failure before re-raise
        raise  # re-raise so Service Bus retries / dead-letters the message


def _finalize_excluded(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.exclusion_reason = reason
    logger.info("Pending Credits: BAN=%s EXCLUDED (%s)", record.ban, reason)


def _finalize_suppressed(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.suppression_reason = reason
    record.handoff_status = HandoffStatus.SUPPRESSED
    logger.info("Pending Credits: BAN=%s SUPPRESSED (%s)", record.ban, reason)
