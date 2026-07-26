"""
Integration test placeholders (TDD Section 13).

These require the Service Bus emulator/real broker and source access, so they
are skipped until the environment is wired. Fill in as access is onboarded.
"""
import pytest


@pytest.mark.skip(reason="Requires Service Bus + source access (not yet onboarded).")
def test_gather_publishes_one_message_per_account():
    ...


@pytest.mark.skip(reason="Requires NotifyNow sandbox credentials.")
def test_processor_hands_off_eligible_record():
    ...
