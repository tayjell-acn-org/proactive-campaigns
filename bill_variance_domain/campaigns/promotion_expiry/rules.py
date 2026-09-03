"""
Promotion Expiry MVP rules (TDD Section 5.1.2).

Notify customers when a promotional discount / bill credit / rate benefit is
approaching expiration or has ended; route to a static self-service page or
approved CTA.

Step mapping (TDD 5.1.2.1) — same 8-step pattern as Pending Credits:
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
from datetime import datetime

logger = get_logger(__name__)

CAMPAIGN_ID = "PROMOTION_EXPIRY"
DOMAIN = "bill_variance_domain"
SERVICE_BUS_CONNECTION = "SERVICE_BUS_CONNECTION"
QUEUE_NAME_SETTING = "SERVICE_BUS_QUEUE_NAME"
BATCH_SIZE = 500


# Step 1 (GATHER) ------------------------------------------------------------ #
def get_candidates(run: CampaignRun, campaign_config: CampaignConfig, queue_name: str) -> int:
   """
   Retrieve promotion expiry records and publish them to Service Bus.

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
           "Using STUB promotion expiry records for %s (Snowflake not wired yet).",
           campaign_config.campaign_id,
       )

   from pathlib import Path

   # Resolve to bill_variance_domain then into shared_packages/test_data
   data_file = (
       Path(__file__).resolve().parents[2]
       / "shared_packages"
       / "test_data"
       / "promotion_expiry_test_data.json"
   )

   logger.debug("Resolved promotion expiry test data path: %s (exists=%s)", str(data_file), data_file.exists())

   if not data_file.exists():
       logger.error("promotion expiry test data not found at %s", str(data_file))
       raise FileNotFoundError(f"promotion expiry test data not found: {data_file}")

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



# Steps 2-8 (PROCESSOR) ------------------------------------------------------ #
def process(work: CampaignWorkMessage) -> None:
   # Get Source context from campaign message
   source_context = work.source_context

   # Step 1: Get Account level items
   acct_info = _get_acct_info(source_context)
   ban = acct_info.get("ban")

   logger.info(
       "Promotion Expiry: processing BAN=%s (run_id=%s)",
       ban,
       work.run_id,
   )

   record = AudienceRecord(
       run_id=work.run_id,
       campaign_id=CAMPAIGN_ID,
       ban=ban,
   )

   config = get_config_loader().get_campaign(
       "bill_variance_domain",
       CAMPAIGN_ID,
   )

   # Step 2: Build Promotions List
   promo_list = _build_promo_list(source_context)

   # Step 3: Get Customer Contact Information
   contact_info = _get_customer_contact_info(source_context)

   # Step 4: Suppression Logic
   # suppression = SuppressionService().check(CAMPAIGN_ID, ban)
   # if suppression.suppressed:
   #     _finalize_suppressed(
   #         record,
   #         suppression.reason or "SUPPRESSED",
   #     )
   #     return

   record.eligibility_status = RecordStatus.ELIGIBLE

   # Step 7: Create and Send Payload to NotifyNow
   if contact_info.get("email"):
       record.payload = _build_notifynow_payload(
           work,
           promo_list,
           acct_info,
           contact_info,
           "email",
       )

       _send_to_notifynow(
           record,
           f"{work.idempotency_key}-email",
           config,
       )

   if contact_info.get("phone"):
       record.payload = _build_notifynow_payload(
           work,
           promo_list,
           acct_info,
           contact_info,
           "sms",
       )

       _send_to_notifynow(
           record,
           f"{work.idempotency_key}-sms",
           config,
       )

   # Step 8: Persist run/eligibility/suppression
   get_sql_repository().upsert_eligibility(record)

   if record.handoff_status == HandoffStatus.HANDED_OFF and config:
       get_sql_repository().record_handoff(
           CAMPAIGN_ID,
           ban,
           work.run_id,
           config.suppression_window_days,
       )

# Step implementations ------------------------------------------------------ #

def _build_promo_list(
   source_context: dict[str, Any],
) -> list[dict[str, Any]]:
   """Build NotifyNow promotion list from source PROMO_DETAILS."""

   promo_list: list[dict[str, Any]] = []

   promo_details = source_context.get("PROMO_DETAILS", []) or []

   for sequence, promo_detail in enumerate(
       promo_details[:3],
       start=1,
   ):
       phone_number = promo_detail.get("PHONE_NUMBER", "") or ""

       promo_list.append(
           {
               "sequence": sequence,
               "promoType": "Trade-In",
               "promoName": "Trade-In",
               "promoAmount": float(
                   promo_detail.get("CREDIT_AMOUNT", 0) or 0
               ),
               "lineLast4": (
                   phone_number[-4:]
                   if phone_number
                   else ""
               ),
           }
       )

   return promo_list


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

   acct_info_dict["ban"] = ban
   acct_info_dict["fan"] = fan

   return acct_info_dict


def _build_notifynow_payload(
   work: CampaignWorkMessage,
   promo: list[dict[str, Any]],
   online_account: dict[str, Any],
   contact: dict[str, Any],
   moc: str,
) -> dict[str, Any]:
   """Step 7: build NotifyNow event payload (TDD Section 5.1.2.2)."""

   if moc == "email":
       return _build_email_payload(
           work,
           promo,
           online_account,
           contact,
       )

   if moc == "sms":
       return _build_sms_payload(
           work,
           promo,
           online_account,
           contact,
       )

   raise ValueError(f"Unsupported method of contact: {moc}")


def _build_email_payload(
   work: CampaignWorkMessage,
   promo: list[dict[str, Any]],
   online_account: dict[str, Any],
   contact: dict[str, Any],
) -> dict[str, Any]:
   """Build NotifyNow Promotion Expiry email payload."""

   transaction_id = (
       f"{work.idempotency_key}-email"
       if work.idempotency_key
       else str(uuid.uuid4())
   )

   recipient_email = contact.get("email", "")
   recipient_name = contact.get("first_name", "")

   source_context = work.source_context or {}

   ban = source_context.get("BAN", "")

   online_registered = (
       "Y"
       if contact.get("online_registered")
       else "N"
   )

   current_bill_cycle_date = (
       source_context.get("CURRENT_BILL_CYCLE_DATE", "")
       or ""
   )

   curr_bill_date = ""
   next_bill_date = ""

   if current_bill_cycle_date:
       bill_date = datetime.strptime(
           current_bill_cycle_date,
           "%Y-%m-%d",
       )

       curr_bill_date = bill_date.strftime("%m-%Y")

       if bill_date.month == 12:
           next_bill_date = f"01-{bill_date.year + 1}"
       else:
           next_bill_date = (
               f"{bill_date.month + 1:02d}-{bill_date.year}"
           )

   promo_details = source_context.get("PROMO_DETAILS", []) or []

   total_expiring_amount = sum(
       float(
           promo_detail.get("CREDIT_AMOUNT", 0)
           or 0
       )
       for promo_detail in promo_details
   )

   current_bill_total = float(
       source_context.get(
           "CURRENT_TOTAL_BALANCE_DUE",
           0,
       )
       or 0
   )

   estimated_next_bill_total = (
       current_bill_total - total_expiring_amount
   )

   payload = {
       "event": {
           "recipientData": [
               {
                   "header": {
                       "source": "PO",
                       "templateId": "PO_PromoExpiry",
                       "scenarioName": "PromotionExpiry",
                       "transactionId": transaction_id,
                   },
                   "notificationOption": [
                       {
                           "moc": "email",
                       }
                   ],
                   "emaildata": {
                       "subject": "Your promotion is expiring",
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
                   "value": "",
               },
               {
                   "name": "onlineRegistered",
                   "value": online_registered,
               },
               {
                   "name": "banLast4",
                   "value": (
                       ban[-4:]
                       if ban
                       else ""
                   ),
               },
               {
                   "name": "currBillDate",
                   "value": curr_bill_date,
               },
               {
                   "name": "nextBillDate",
                   "value": next_bill_date,
               },
               {
                   "name": "currentBillTotal",
                   "value": current_bill_total,
               },
               {
                   "name": "estimatedNextBillTotal",
                   "value": estimated_next_bill_total,
               },
               {
                   "name": "totalExpiringPromos",
                   "value": int(
                       source_context.get(
                           "CURRENT_PROMO_COUNT",
                           0,
                       )
                       or 0
                   ),
               },
               {
                   "name": "totalExpiringAmount",
                   "value": total_expiring_amount,
               },
               {
                   "name": "promoList",
                   "value": promo[:3],
               },
           ],
       }
   }

   logger.debug(
       "NotifyNow Promotion Expiry email payload built: %s",
       payload,
   )

   return payload


def _build_sms_payload(
   work: CampaignWorkMessage,
   promo: list[dict[str, Any]],
   online_account: dict[str, Any],
   contact: dict[str, Any],
) -> dict[str, Any]:
   """Build NotifyNow Promotion Expiry SMS payload."""

   transaction_id = (
       f"{work.idempotency_key}-sms"
       if work.idempotency_key
       else str(uuid.uuid4())
   )

   request_id = (
       f"{transaction_id}-req-{uuid.uuid4()}"
   )

   phone_number = contact.get("phone", "")
   recipient_name = contact.get("first_name", "")

   source_context = work.source_context or {}

   ban = source_context.get("BAN", "")

   online_registered = (
       "Y"
       if contact.get("online_registered")
       else "N"
   )

   current_bill_cycle_date = (
       source_context.get("CURRENT_BILL_CYCLE_DATE", "")
       or ""
   )

   curr_bill_date = ""
   next_bill_date = ""

   if current_bill_cycle_date:
       bill_date = datetime.strptime(
           current_bill_cycle_date,
           "%Y-%m-%d",
       )

       curr_bill_date = bill_date.strftime("%m-%Y")

       if bill_date.month == 12:
           next_bill_date = f"01-{bill_date.year + 1}"
       else:
           next_bill_date = (
               f"{bill_date.month + 1:02d}-{bill_date.year}"
           )

   promo_details = source_context.get("PROMO_DETAILS", []) or []

   total_expiring_amount = sum(
       float(
           promo_detail.get("CREDIT_AMOUNT", 0)
           or 0
       )
       for promo_detail in promo_details
   )

   current_bill_total = float(
       source_context.get(
           "CURRENT_TOTAL_BALANCE_DUE",
           0,
       )
       or 0
   )

   estimated_next_bill_total = (
       current_bill_total - total_expiring_amount
   )

   payload = {
       "event": {
           "recipientData": [
               {
                   "header": {
                       "source": "PO",
                       "templateId": "PO_PromoExpiry_SMS",
                       "scenarioName": "PromotionExpiry",
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
                   "attribData": [
                       {
                           "name": "customerFirstName",
                           "value": recipient_name,
                       },
                       {
                           "name": "customerPlatform",
                           "value": "",
                       },
                       {
                           "name": "onlineRegistered",
                           "value": online_registered,
                       },
                       {
                           "name": "banLast4",
                           "value": (
                               ban[-4:]
                               if ban
                               else ""
                           ),
                       },
                       {
                           "name": "currBillDate",
                           "value": curr_bill_date,
                       },
                       {
                           "name": "nextBillDate",
                           "value": next_bill_date,
                       },
                       {
                           "name": "currentBillTotal",
                           "value": current_bill_total,
                       },
                       {
                           "name": "estimatedNextBillTotal",
                           "value": estimated_next_bill_total,
                       },
                       {
                           "name": "totalExpiringPromos",
                           "value": int(
                               source_context.get(
                                   "CURRENT_PROMO_COUNT",
                                   0,
                               )
                               or 0
                           ),
                       },
                       {
                           "name": "totalExpiringAmount",
                           "value": total_expiring_amount,
                       },
                       {
                           "name": "promoList",
                           "value": promo[:3],
                       },
                   ],
               }
           ],
       }
   }

   logger.debug(
       "NotifyNow Promotion Expiry SMS payload built: %s",
       payload,
   )

   return payload


def _send_to_notifynow(
   record: AudienceRecord,
   idempotency_key: str,
   config
) -> None:
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
    logger.info("Promotion Expiry: BAN=%s EXCLUDED (%s)", record.ban, reason)
    get_sql_repository().upsert_eligibility(record)


def _finalize_suppressed(record: AudienceRecord, reason: str) -> None:
    record.eligibility_status = RecordStatus.EXCLUDED
    record.suppression_reason = reason
    record.handoff_status = HandoffStatus.SUPPRESSED
    logger.info("Promotion Expiry: BAN=%s SUPPRESSED (%s)", record.ban, reason)
    get_sql_repository().upsert_eligibility(record)
