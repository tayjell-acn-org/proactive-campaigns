"""Unit tests for shared campaign models (serialization + idempotency)."""
from shared_packages.campaign_models import (
    CampaignWorkMessage, CampaignConfig, RecordStatus, HandoffStatus,
)


def test_work_message_roundtrip_with_source_context():
    msg = CampaignWorkMessage(
        run_id="run-1", campaign_id="PENDING_CREDITS", domain="BILL_VARIANCE",
        ban="123456789", source_context={"credit": {"credit_amount": 235.90}},
    )
    parsed = CampaignWorkMessage.from_json(msg.to_json())
    assert parsed.ban == "123456789"
    assert parsed.source_context["credit"]["credit_amount"] == 235.90
    assert parsed.idempotency_key == "run-1:PENDING_CREDITS:123456789"


def test_work_message_idempotency_key_stable():
    a = CampaignWorkMessage(run_id="r", campaign_id="c", domain="d", ban="9")
    b = CampaignWorkMessage(run_id="r", campaign_id="c", domain="d", ban="9")
    assert a.idempotency_key == b.idempotency_key


def test_campaign_config_from_dict_ignores_unknown():
    cfg = CampaignConfig.from_dict({
        "campaign_id": "PENDING_CREDITS", "campaign_name": "Pending Credits",
        "active_flag": True, "unexpected_field": "ignore me",
    })
    assert cfg.campaign_id == "PENDING_CREDITS"
    assert cfg.active_flag is True
    assert cfg.suppression_window_days == 30


def test_status_enums():
    assert RecordStatus.HANDOFF_FAILED.value == "HANDOFF_FAILED"
    assert HandoffStatus.SUPPRESSED.value == "SUPPRESSED"
