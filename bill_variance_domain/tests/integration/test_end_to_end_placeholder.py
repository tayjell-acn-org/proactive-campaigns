"""
Integration test placeholders (TDD Section 13). Require Service Bus + source
+ NotifyNow + Azure SQL DB access, so skipped until the environment is wired.
"""
import pytest


@pytest.mark.skip(reason="Requires Service Bus + source access (not yet onboarded).")
def test_gather_publishes_one_message_per_account():
    ...


@pytest.mark.skip(reason="Requires NotifyNow sandbox + Azure SQL DB.")
def test_processor_hands_off_and_persists_eligibility():
    ...
