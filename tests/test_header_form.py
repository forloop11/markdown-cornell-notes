"""Tests for app/header_form.py: the header form <-> stored header field
round-trip behind the editor app's date/time/timezone pickers.
"""
import datetime

import header_form


def blank_fields(**overrides):
    fields = {"topic": "", "date": "", "attendees": "", "time": "", "timezone": "", "location": ""}
    fields.update(overrides)
    return fields


def test_parse_time_field_legacy_convention():
    """The legacy "HH:MM--HH:MM TZ, location" form is split back apart."""
    start, end, tz_hint, location = header_form.parse_time_field("10:00--10:30 EDT, Teams")
    assert (start, end, tz_hint, location) == (datetime.time(10, 0), datetime.time(10, 30), "EDT", "Teams")


def test_parse_time_field_free_text_becomes_location():
    """Something that isn't a time range at all is kept, as location."""
    assert header_form.parse_time_field("Lunch, Room 4") == (None, None, "", "Lunch, Room 4")


def test_compose_time_field_uses_zone_abbreviation_for_date():
    """The abbreviation follows DST for the meeting's date."""
    summer = header_form.compose_time_field(
        datetime.time(10), datetime.time(10, 30), "America/Los_Angeles", datetime.date(2026, 7, 1)
    )
    winter = header_form.compose_time_field(
        datetime.time(10), None, "America/Los_Angeles", datetime.date(2026, 1, 15)
    )
    assert summer == "10:00--10:30 PDT"
    assert winter == "10:00 PST"


def test_compose_time_field_zone_wins_over_hint():
    """A real dropdown pick replaces a hint carried over from load."""
    composed = header_form.compose_time_field(
        datetime.time(9), None, "Europe/London", datetime.date(2026, 1, 15), tz_hint="EDT"
    )
    assert composed == "09:00 GMT"
    assert header_form.compose_time_field(datetime.time(9), None, "", None, tz_hint="EDT") == "09:00 EDT"


def test_form_from_header_defaults_blank_date_to_today():
    """A freshly created file's form starts on today's date."""
    form = header_form.form_from_header(blank_fields(), today=datetime.date(2026, 10, 5))
    assert form["date"] == "2026-10-05"


def test_form_from_header_migrates_legacy_time_field():
    """A pre-timezone/location entry loads with its location and hint
    split out of "time".
    """
    form = header_form.form_from_header(blank_fields(date="2026-08-25", time="10:00--10:30 EDT, Teams"))
    assert form["start"] == "10:00"
    assert form["end"] == "10:30"
    assert form["tz_hint"] == "EDT"
    assert form["location"] == "Teams"
    assert form["timezone"] == ""


def test_form_header_round_trip():
    """Loading a saved header into the form and saving it back is lossless."""
    fields = blank_fields(
        topic="Weekly Sync",
        date="2026-08-23",
        attendees="Lily, Amber",
        time="10:00--10:30 EDT",
        timezone="America/Detroit",
        location="Zoom",
    )
    assert header_form.header_from_form(header_form.form_from_header(fields)) == fields


def test_header_from_form_ignores_invalid_values():
    """Malformed browser input degrades to blank rather than raising."""
    fields = header_form.header_from_form(
        {"topic": 5, "date": "not-a-date", "start": "25:99", "timezone": "Mars/Base", "location": None}
    )
    assert fields == blank_fields()
