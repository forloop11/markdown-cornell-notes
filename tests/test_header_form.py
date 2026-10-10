"""Tests for app/header_form.py: the header form <-> stored header field
round-trip behind the editor's date/time/timezone fields.
"""
from datetime import date, time

import header_form as hf


def blank_fields(**overrides):
    return {"topic": "", "date": "", "attendees": "", "time": "", "timezone": "", "location": "", **overrides}


def test_legacy_time_field_is_split_back_apart():
    assert hf.parse_time_field("10:00--10:30 EDT, Teams") == (time(10), time(10, 30), "EDT", "Teams")


def test_free_text_that_isnt_a_time_range_is_kept_as_location():
    assert hf.parse_time_field("Lunch, Room 4") == (None, None, "", "Lunch, Room 4")


def test_zone_abbreviation_follows_dst_for_the_meetings_date():
    assert hf.compose_time_field(time(10), time(10, 30), "America/Los_Angeles", date(2026, 7, 1)) == "10:00--10:30 PDT"
    assert hf.compose_time_field(time(10), None, "America/Los_Angeles", date(2026, 1, 15)) == "10:00 PST"


def test_abbreviations_for_zones_around_the_world():
    assert hf.tz_abbrev("Europe/London", date(2026, 7, 1), time(12)) == "BST"
    assert hf.tz_abbrev("Europe/Berlin", date(2026, 1, 15), time(12)) == "CET"
    assert hf.tz_abbrev("Australia/Sydney", date(2026, 1, 15), time(12)) == "AEDT"
    assert hf.tz_abbrev("Asia/Tokyo", date(2026, 1, 15), time(12)) == "JST"
    assert hf.tz_abbrev("UTC", date(2026, 1, 15), time(12)) == "UTC"


def test_a_zone_with_no_abbreviation_gets_its_offset():
    assert hf.tz_abbrev("America/Sao_Paulo", date(2026, 1, 15), time(12)) == "-03"
    assert hf.tz_abbrev("Asia/Kathmandu", date(2026, 1, 15), time(12)) == "+0545"


def test_abbreviation_uses_the_meetings_own_time_on_a_dst_change_day():
    # US DST starts 2026-03-08 at 02:00 local.
    assert hf.tz_abbrev("America/New_York", date(2026, 3, 8), time(1)) == "EST"
    assert hf.tz_abbrev("America/New_York", date(2026, 3, 8), time(9)) == "EDT"


def test_an_unrecognized_zone_name_is_passed_through():
    assert hf.tz_abbrev("Mars/Base", date(2026, 1, 15), time(12)) == "Mars/Base"


def test_a_real_zone_pick_replaces_a_hint_carried_over_from_load():
    assert hf.compose_time_field(time(9), None, "Europe/London", date(2026, 1, 15), "EDT") == "09:00 GMT"
    assert hf.compose_time_field(time(9), None, "", None, "EDT") == "09:00 EDT"


def test_a_freshly_created_files_form_starts_on_todays_date():
    assert hf.form_from_header(blank_fields(), today=date(2026, 10, 5))["date"] == "2026-10-05"


def test_a_pre_timezone_entry_loads_with_location_and_hint_split_out_of_time():
    form = hf.form_from_header(blank_fields(date="2026-08-25", time="10:00--10:30 EDT, Teams"))
    assert form["start"] == "10:00"
    assert form["end"] == "10:30"
    assert form["tz_hint"] == "EDT"
    assert form["location"] == "Teams"
    assert form["timezone"] == ""


def test_loading_a_saved_header_into_the_form_and_saving_it_back_is_lossless():
    fields = blank_fields(
        topic="Weekly Sync",
        date="2026-08-23",
        attendees="Lily, Amber",
        time="10:00--10:30 EDT",
        timezone="America/Detroit",
        location="Zoom",
    )
    assert hf.header_from_form(hf.form_from_header(fields)) == fields


def test_malformed_form_input_degrades_to_blank_rather_than_raising():
    form = {"topic": 5, "date": "not-a-date", "start": "25:99", "timezone": "Mars/Base", "location": None}
    assert hf.header_from_form(form) == blank_fields()


def test_impossible_calendar_dates_are_rejected():
    assert hf.parse_iso_date("2026-02-30") is None
    assert hf.parse_iso_date("2026-2-3") == date(2026, 2, 3)


def test_timezone_options_include_utc_and_real_zones():
    assert "UTC" in hf.TZ_OPTIONS
    assert "America/Detroit" in hf.TZ_OPTIONS
    assert "Factory" not in hf.TZ_OPTIONS
