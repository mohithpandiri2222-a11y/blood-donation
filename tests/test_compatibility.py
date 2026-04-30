# tests/test_compatibility.py
import pytest
from compatibility import can_donate, COMPATIBLE_DONORS

GROUPS = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+']

# Ground-truth compatibility table (recipient -> valid donors)
TRUTH = {
    'O-':  {'O-'},
    'O+':  {'O-', 'O+'},
    'A-':  {'O-', 'A-'},
    'A+':  {'O-', 'O+', 'A-', 'A+'},
    'B-':  {'O-', 'B-'},
    'B+':  {'O-', 'O+', 'B-', 'B+'},
    'AB-': {'O-', 'A-', 'B-', 'AB-'},
    'AB+': {'O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'},
}

# Generate all 64 combinations
@pytest.mark.parametrize("donor,recipient", [
    (d, r) for r in GROUPS for d in GROUPS
])
def test_compatibility_matrix(donor, recipient):
    expected = donor in TRUTH[recipient]
    result   = can_donate(donor, recipient)
    assert result == expected, (
        f"can_donate('{donor}', '{recipient}') "
        f"returned {result}, expected {expected}"
    )


def test_all_groups_covered():
    """Every blood group must be a key in COMPATIBLE_DONORS."""
    for g in GROUPS:
        assert g in COMPATIBLE_DONORS, f"{g} missing from COMPATIBLE_DONORS"


def test_o_negative_universal_donor():
    """O- must be able to donate to ALL recipients."""
    for recipient in GROUPS:
        assert can_donate('O-', recipient), \
            f"O- should donate to {recipient}"


def test_ab_positive_universal_recipient():
    """AB+ must accept from ALL donors."""
    for donor in GROUPS:
        assert can_donate(donor, 'AB+'), \
            f"AB+ should accept from {donor}"


def test_incompatible_pairs():
    """Spot-check known incompatible pairs."""
    assert not can_donate('A+', 'O-')
    assert not can_donate('B+', 'A+')
    assert not can_donate('AB-', 'B-')
    assert not can_donate('A+', 'B+')
