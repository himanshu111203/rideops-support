"""Required information per category before escalating to engineering.

ASSUMPTION: the ticket data does not record what information was attached to a
ticket. These lists are the author's assumptions about what engineering needs,
labelled as such in the app and the write-up.
"""
from __future__ import annotations

ASSUMPTION_NOTE = ("Checklist items are assumptions, not from the data: the tickets "
                   "don't record what information was attached.")

COMMON = ["Client ID and affected employee IDs", "Date/time of the issue (IST)"]

CHECKLISTS: dict[str, list[str]] = {
    "Roster / booking not syncing": [
        "Uploaded roster file attached", "Shift time(s) affected",
        "Booking cutoff setting screenshot", "Number of employees missing / duplicated",
    ],
    "Live tracking / GPS incorrect": [
        "Trip ID", "Driver app version", "Screenshot of map vs actual location",
    ],
    "Report export failing": [
        "Report name and date range", "Export format (Excel/CSV/PDF)",
        "Screenshot of error or blank file", "Check known-issue board first",
    ],
    "Cab delay / no-show complaint": [
        "Trip ID", "Route number", "Shift time", "Driver GPS log checked",
    ],
    "How-to / feature request": [
        "Confirm it's not covered in the help docs", "Business need in one line",
    ],
    "Login / access issue": [
        "User email(s)", "SSO or password login", "Role/permission screen screenshot",
    ],
    "OTP / boarding issue": [
        "Trip ID", "Employee phone (masked) and app version", "Driver app version",
    ],
    "Billing / invoice discrepancy": [
        "Invoice number", "Client's trip count / records attached", "Rate card config screenshot",
    ],
    "Employee address / geocode change": [
        "Employee ID", "Old and new address", "Address change date", "Geocode pin screenshot",
    ],
    "Driver / vehicle compliance docs": [
        "Vehicle / driver ID", "Document type and expiry date", "Upload error screenshot",
    ],
}

# Config checks L1 can try before escalating (used by the "Try resolving at L1" branch).
CONFIG_CHECKS: dict[str, list[str]] = {
    "Roster / booking not syncing": [
        "Booking cutoff time matches client policy", "Roster re-synced after cutoff change",
        "Excel template columns match the current version",
    ],
    "Employee address / geocode change": [
        "Address change saved and approved by admin", "Routing re-run after address change",
    ],
    "Billing / invoice discrepancy": [
        "Correct rate card mapped to the vendor", "Toll/dead-km rules configured for client",
    ],
    "Login / access issue": [
        "User role grants the module", "SSO mapping for the user's domain",
    ],
    "How-to / feature request": [
        "Answer from help docs / known how-to list",
    ],
}
DEFAULT_CONFIG_CHECKS = ["Client configuration screen reviewed", "Known how-to answers checked"]


def checklist_for(category: str) -> list[str]:
    return COMMON + CHECKLISTS.get(category, [])


def config_checks_for(category: str) -> list[str]:
    return CONFIG_CHECKS.get(category, DEFAULT_CONFIG_CHECKS)
