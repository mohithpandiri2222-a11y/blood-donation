# compatibility.py

COMPATIBLE_DONORS = {
    'O-':  ['O-'],
    'O+':  ['O-', 'O+'],
    'A-':  ['O-', 'A-'],
    'A+':  ['O-', 'O+', 'A-', 'A+'],
    'B-':  ['O-', 'B-'],
    'B+':  ['O-', 'O+', 'B-', 'B+'],
    'AB-': ['O-', 'A-', 'B-', 'AB-'],
    'AB+': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],
}

def can_donate(donor_group, recipient_group):
    """Returns True if donor_group can donate to recipient_group."""
    if recipient_group not in COMPATIBLE_DONORS:
        return False
    return donor_group in COMPATIBLE_DONORS[recipient_group]

def get_compatible_donors(recipient_group):
    """Returns a list of donor groups that can donate to the recipient_group."""
    return COMPATIBLE_DONORS.get(recipient_group, [])
