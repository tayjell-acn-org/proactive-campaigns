"""Unit tests for shared campaign models (serialization + idempotency)."""
import json

from shared_packages.campaign_models import (
    CampaignWorkMessage,
    CampaignConfig,
    RecordStatus,
)


def test_work_message_roundtrip():
    msg = CampaignWorkMessage(
        run_id="run-1",
        campaign_id="PENDING_CREDITS",
        domain="BILL_VARIANCE",
        ban="123456789",
    )
    raw = msg.to_json()
    parsed = CampaignWorkMessage.from_json(raw)

    assert parsed.run_id == "run-1"
    assert parsed.campaign_id == "PENDING_CREDITS"
    assert parsed.ban == "123456789"
    # idempotency_key is derived and stable
    assert parsed.idempotency_key == "run-1:PENDING_CREDITS:123456789"


def test_work_message_idempotency_key_stable():
    a = CampaignWorkMessage(run_id="r", campaign_id="c", domain="d", ban="9")
    b = CampaignWorkMessage(run_id="r", campaign_id="c", domain="d", ban="9")
    assert a.idempotency_key == b.idempotency_key


def test_campaign_config_from_dict_ignores_unknown():
    cfg = CampaignConfig.from_dict(
        {
            "campaign_id": "PENDING_CREDITS",
            "campaign_name": "Pending Credits",
            "active_flag": True,
            "unexpected_field": "ignore me",
        }
    )
    assert cfg.campaign_id == "PENDING_CREDITS"
    assert cfg.active_flag is True


def test_record_status_values():
    assert RecordStatus.ELIGIBLE.value == "ELIGIBLE"
    assert RecordStatus.HANDOFF_FAILED.value == "HANDOFF_FAILED"
