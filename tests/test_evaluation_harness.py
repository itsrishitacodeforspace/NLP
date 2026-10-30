"""Lock the synthetic evaluation results: no silent regressions, no silent resolutions."""
from __future__ import annotations

import pytest

from nlp.evaluation import run_all

# Cases that are expected to FAIL today. Each is documented with a
# ``known_limitation`` note on the case itself. This set is the honest record of
# unresolved behaviour; it is asserted explicitly so a limitation cannot be
# hidden and a fix cannot silently "resolve" a case without this list changing.
EXPECTED_KNOWN_LIMITATIONS = {
    "liability_cap_in_crossref",
    "obligation_passive",
}


@pytest.fixture(scope="module")
def report():
    return run_all()


def test_no_unexpected_regressions(report):
    """Every failing case must be a declared known limitation."""
    assert report.unexpected_failures == set(), (
        "unexpected evaluation failures (new regressions): "
        f"{sorted(report.unexpected_failures)}"
    )


def test_known_limitations_match_declared(report):
    """The failing set must equal the documented known-limitation set.

    If a fix makes a known-limitation case pass, this test fails on purpose so
    the stale ``known_limitation`` note is removed and the report regenerated.
    """
    assert report.failing_case_ids == EXPECTED_KNOWN_LIMITATIONS, (
        f"declared known limitations {sorted(EXPECTED_KNOWN_LIMITATIONS)} != "
        f"observed failing {sorted(report.failing_case_ids)}"
    )


def test_case_known_limitation_notes_are_present(report):
    """Each expected-failing case carries an explanatory note (no blank failures)."""
    for cr in report.case_results:
        if cr.case.case_id in EXPECTED_KNOWN_LIMITATIONS:
            assert cr.case.known_limitation, f"{cr.case.case_id} must document its limitation"


def test_evidence_integrity_invariants_hold(report):
    """Model findings stay unverified; rule findings are traceable; contract-level scoped."""
    violated = [inv for inv in report.invariants if not inv.ok]
    assert not violated, "evidence-integrity invariants violated: " + "; ".join(
        f"{inv.name}: {inv.violations[:5]}" for inv in violated
    )
