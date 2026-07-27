"""Unit tests for the suppression service (Step 3) against the SQL repository."""
from shared_packages.base_db import SqlRepository, get_sql_repository
from shared_packages.campaign_models import AudienceRecord, HandoffStatus, RecordStatus
from shared_packages.suppression import SuppressionService


def test_not_suppressed_when_no_history():
    result = SuppressionService().check("PENDING_CREDITS", "ban-new")
    assert result.suppressed is False


def test_suppressed_within_window_after_handoff():
    repo = get_sql_repository()  # in-memory (no SQL_CONNECTION_STRING)
    # Record a handoff with a 30-day window, then confirm suppression.
    rec = AudienceRecord(
        run_id="r1", campaign_id="PENDING_CREDITS", ban="ban-1",
        eligibility_status=RecordStatus.HANDED_OFF, handoff_status=HandoffStatus.HANDED_OFF,
    )
    repo.upsert_eligibility(rec)
    repo.record_handoff("PENDING_CREDITS", "ban-1", "r1", suppression_window_days=30)

    result = SuppressionService().check("PENDING_CREDITS", "ban-1")
    assert result.suppressed is True
    assert result.reason == "WITHIN_SUPPRESSION_WINDOW"
