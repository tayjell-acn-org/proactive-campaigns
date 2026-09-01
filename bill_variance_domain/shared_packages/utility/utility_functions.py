"""Utilities for bill_variance_domain.
"""

import os

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from shared_packages.campaign_models import CampaignWorkMessage
from shared_packages.campaign_models.models import CampaignRun

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
                    #account_id=candidate.get("account_id", ""),
                    #ban=candidate.get("ban", ""),
                    
                    source_context = candidate

                    # source_context={
                    #     "credit": {
                    #         "credit_amount": float(
                    #             candidate.get("pendingCreditAmount",
                    #                           candidate.get("PENDING_CREDIT_AMOUNT",
                    #                                         candidate.get("CREDIT_AMOUNT", 0.0))) or 0.0
                    #         ),
                    #         "credits": candidate.get("credits") if isinstance(candidate.get("credits"), list) else None,
                    #         "platform": candidate.get("PLATFORM_HANDLER", candidate.get("platform")),
                    #         "effective_date": candidate.get("pendingCreditEffectiveDate",
                    #                                          candidate.get("PENDING_CREDIT_EFFECTIVE_DATE",
                    #                                                        candidate.get("EFFECTIVE_DATE", ""))),
                    #         "bill_close_day": candidate.get("billCloseDay", candidate.get("BILL_CLOSE_DAY", 0)),
                    #         "ban": candidate.get("ban", candidate.get("BAN", "")),
                    #     }
                    # },
               )
               print("SOURCE_CONTEXT: " + str(work.source_context))
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
