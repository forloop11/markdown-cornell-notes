"""Conversion between a markdown file's stored header fields (see
pipeline.HEADER_FIELDS) and the header form the editor UI edits:
Topic/Location, a Date picker, Start/End time fields, a Timezone field,
and Attendees.

The form doesn't map 1:1 onto the stored fields -- "time" is composed
from Start/End/Timezone (e.g. "10:00--10:30 PDT"), and an entry written
with the legacy "HH:MM--HH:MM TZ, location" convention is parsed back
apart on load -- so that round-trip lives here, where zoneinfo can work
out each zone's abbreviation for the chosen date.
"""
import datetime
import re
import zoneinfo

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"

# "Factory" is a tzdata placeholder, not a real zone -- not useful to offer.
TZ_OPTIONS = sorted(z for z in zoneinfo.available_timezones() if z != "Factory")
_TZ_SET = frozenset(TZ_OPTIONS)

# The form's keys, as the window fills and reads them (see window.py).
FORM_FIELDS = ["topic", "location", "date", "start", "end", "timezone", "tz_hint", "attendees"]

# Recognizes the legacy "time" field convention "HH:MM--HH:MM TZ, location"
# (also accepting a single "-"/en dash, or "to" for the range) -- from
# before "timezone"/"location" were their own fields, when the editor baked
# both into "time" (e.g. "10:00--10:30 EDT, Teams"). Only used as a
# fallback in form_from_header, for values not covered by those fields
# (hand-edited entries, or ones written before they existed), so such
# entries still show their start/end/location correctly on first load. An
# abbreviation like "EDT" doesn't map back to one specific IANA zone, so
# it's kept as tz_hint (passed through as-is by compose_time_field) rather
# than resolved to a real zone in the picker.
TIME_RANGE_RE = re.compile(
    r"^\s*(?P<start>\d{1,2}:\d{2})"
    r"(?:\s*(?:--|-|–|to)\s*(?P<end>\d{1,2}:\d{2}))?"
    r"(?:\s+(?P<tzhint>[A-Z]{2,6}))?"
    r"\s*,?\s*(?P<location>.*?)\s*$",
    re.DOTALL,
)


def parse_iso_date(value):
    """Parse a "YYYY-MM-DD" string into a datetime.date, or None if
    `value` isn't one.
    """
    try:
        return datetime.datetime.strptime(value, DATE_FORMAT).date()
    except (TypeError, ValueError):
        return None


def parse_hhmm(value):
    """Parse an "HH:MM" string into a datetime.time, or None if `value`
    is blank or isn't one.
    """
    try:
        return datetime.datetime.strptime(value, TIME_FORMAT).time()
    except (TypeError, ValueError):
        return None


def parse_time_field(value):
    """Parse a "time" header field (TIME_RANGE_RE's legacy
    "HH:MM--HH:MM TZ, location" convention, or anything looser) into
    (start, end, tz_hint, location) -- start/end as datetime.time (or
    None), tz_hint/location as strings.
    """
    match = TIME_RANGE_RE.match(value or "")
    if not match:
        return None, None, "", (value or "").strip()
    return (
        parse_hhmm(match.group("start")),
        parse_hhmm(match.group("end")),
        match.group("tzhint") or "",
        match.group("location"),
    )


def tz_abbrev(tz_name, ref_date, ref_time):
    """The abbreviation (e.g. "PDT") for IANA zone `tz_name` at
    `ref_date`/`ref_time` (today/noon if either is None, since only the
    date determines DST for most zones) -- or `tz_name` itself if it
    isn't a recognized zone.
    """
    try:
        zone = zoneinfo.ZoneInfo(tz_name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return tz_name
    dt = datetime.datetime.combine(
        ref_date or datetime.date.today(), ref_time or datetime.time(12, 0), tzinfo=zone
    )
    return dt.tzname() or tz_name


def compose_time_field(start, end, tz_name, ref_date, tz_hint=""):
    """Compose the "time" header field's string (e.g. "10:00--10:30 PDT")
    from the Start/End times and the Timezone field.
    """
    # Location isn't folded in here -- it's written to its own "location"
    # field and recombined with this one for display by
    # settings/template.tex's \cnHdrTimeLine.
    if start and end:
        time_part = f"{start.strftime(TIME_FORMAT)}--{end.strftime(TIME_FORMAT)}"
    elif start:
        time_part = start.strftime(TIME_FORMAT)
    else:
        time_part = ""

    # A real zone pick always wins over a hint carried from the last
    # load (see parse_time_field) -- once the user actually chooses a zone,
    # the hint's job (preventing round-trip data loss) is done.
    abbrev = tz_abbrev(tz_name, ref_date, start) if tz_name else tz_hint
    if abbrev:
        time_part = f"{time_part} {abbrev}".strip()

    return time_part


def form_from_header(fields, today=None):
    """The header form's initial values for stored header `fields` (a dict
    covering every name in pipeline.HEADER_FIELDS).
    """
    start, end, tz_hint, location = parse_time_field(fields["time"])
    date = parse_iso_date(fields["date"]) or today or datetime.date.today()
    return {
        "topic": fields["topic"],
        # fields["location"] is what the Location field wrote on a previous
        # save; an entry that predates that field falls back to whatever's
        # parsed out of the "time" text.
        "location": fields["location"] or location,
        # A file with no date yet (freshly created) starts the picker on
        # today rather than blank -- the window saves the form right after
        # loading it, so this also becomes the stored value.
        "date": date.strftime(DATE_FORMAT),
        "start": start.strftime(TIME_FORMAT) if start else "",
        "end": end.strftime(TIME_FORMAT) if end else "",
        # fields["timezone"] is the IANA zone name the picker wrote on a
        # previous save; an entry that predates that field, or one
        # hand-edited to something no longer a valid zone, falls back to
        # unset -- the abbreviation in tz_hint still shows through then.
        "timezone": fields["timezone"] if fields["timezone"] in _TZ_SET else "",
        "tz_hint": tz_hint,
        "attendees": fields["attendees"],
    }


def header_from_form(form):
    """The stored header fields (every name in pipeline.HEADER_FIELDS) for
    header form values `form`, as read from the window. Missing or
    non-string values are treated as blank, and an unrecognized timezone
    or malformed date/time as unset.
    """
    values = {name: form.get(name) for name in FORM_FIELDS}
    values = {name: value if isinstance(value, str) else "" for name, value in values.items()}

    ref_date = parse_iso_date(values["date"])
    tz_name = values["timezone"] if values["timezone"] in _TZ_SET else ""
    return {
        "topic": values["topic"],
        "date": ref_date.strftime(DATE_FORMAT) if ref_date else "",
        "attendees": values["attendees"],
        "time": compose_time_field(
            parse_hhmm(values["start"]), parse_hhmm(values["end"]), tz_name, ref_date, values["tz_hint"]
        ),
        # The picker's actual IANA zone name (distinct from the
        # abbreviation baked into "time" above), so the exact zone can be
        # restored next time this file is opened.
        "timezone": tz_name,
        "location": values["location"],
    }
