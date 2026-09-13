"""Utilities for bill_variance_domain."""

import os

from azure.servicebus import ServiceBusClient, ServiceBusMessage
from cryptography.fernet import Fernet

from shared_packages.campaign_models import CampaignWorkMessage
from shared_packages.campaign_models.models import CampaignRun

FERNET_KEY = os.environ["FERNET_KEY"]
HMAC_SECRET = os.environ["HMAC_SECRET"].encode()


def _publish_work_messages(
    run: CampaignRun,
    campaign_id: str,
    candidates: list[dict],
    connection_setting: str,
    queue_name: str,
) -> int:

    connection_string = os.environ[connection_setting]
    FERNET = Fernet(FERNET_KEY.encode())

    count = 0

    with ServiceBusClient.from_connection_string(connection_string) as sb_client:
        with sb_client.get_queue_sender(queue_name=queue_name) as sender:
            batch = sender.create_message_batch()

            for candidate in candidates:
                work = CampaignWorkMessage(
                    run_id=run.run_id,
                    campaign_id=campaign_id,
                    start_ds=run.start_ds,
                    ban=candidate.get("BAN"),
                    domain="BILL_VARIANCE",
                    source_context=candidate,
                )

                encrypted_body = FERNET.encrypt(
                    work.to_json().encode("utf-8")
                )

                message = ServiceBusMessage(
                    body=encrypted_body,
                    content_type="application/fernet+json",
                    message_id=work.idempotency_key,
                    correlation_id=work.correlation_id,
                )

                try:
                    batch.add_message(message)
                except ValueError:
                    sender.send_messages(batch)
                    batch = sender.create_message_batch()
                    batch.add_message(message)

                count += 1

            if len(batch) > 0:
                sender.send_messages(batch)

    return count