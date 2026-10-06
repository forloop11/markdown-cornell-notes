// Conversion between a markdown file's stored header fields (see
// pipeline.js's HEADER_FIELDS) and the header form the editor UI edits:
// Topic/Location, a Date picker, Start/End time pickers, a Timezone field,
// and Attendees.
//
// The form doesn't map 1:1 onto the stored fields -- "time" is composed
// from Start/End/Timezone (e.g. "10:00--10:30 PDT"), and an entry written
// with the legacy "HH:MM--HH:MM TZ, location" convention is parsed back
// apart on load -- so that round-trip lives here, in the main process,
// where Intl can work out each zone's abbreviation for the chosen date.
"use strict";

// Intl's list is canonical zones only and leaves out plain "UTC", which
// tzdata (and so the old Python editor) offered -- add it back.
const TZ_OPTIONS = [...new Set([...Intl.supportedValuesOf("timeZone"), "UTC"])].sort();

// The form's keys, as sent to and received from the renderer (see
// renderer/app.js).
const FORM_FIELDS = ["topic", "location", "date", "start", "end", "timezone", "tz_hint", "attendees"];

// Recognizes the legacy "time" field convention "HH:MM--HH:MM TZ, location"
// (also accepting a single "-"/en dash, or "to" for the range) -- from
// before "timezone"/"location" were their own fields, when the editor baked
// both into "time" (e.g. "10:00--10:30 EDT, Teams"). Only used as a
// fallback in formFromHeader, for values not covered by those fields
// (hand-edited entries, or ones written before they existed), so such
// entries still show their start/end/location correctly on first load. An
// abbreviation like "EDT" doesn't map back to one specific IANA zone, so
// it's kept as tz_hint (passed through as-is by composeTimeField) rather
// than resolved to a real zone in the picker.
const TIME_RANGE_RE =
  /^\s*(?<start>\d{1,2}:\d{2})(?:\s*(?:--|-|–|to)\s*(?<end>\d{1,2}:\d{2}))?(?:\s+(?<tzhint>[A-Z]{2,6}))?\s*,?\s*(?<location>.*?)\s*$/s;

// Locales whose short zone names are tried in order for an abbreviation:
// each only knows the abbreviations local to it (en-US has EDT/PDT, en-GB
// has BST/CET, en-AU has AEST, en-IN has IST, ja-JP has JST), and the
// rest just give "GMT+N".
const ABBREV_LOCALES = ["en-US", "en-GB", "en-AU", "en-IN", "en-NZ", "ja-JP"];

const pad2 = (n) => String(n).padStart(2, "0");

// A calendar date as {year, month, day} (month 1-12) -- plain values, not
// a Date, so no local timezone ever gets involved.
function parseIsoDate(value) {
  const match = typeof value === "string" && /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(value);
  if (!match) return null;
  const [year, month, day] = match.slice(1).map(Number);
  const check = new Date(Date.UTC(year, month - 1, day));
  if (check.getUTCFullYear() !== year || check.getUTCMonth() !== month - 1 || check.getUTCDate() !== day) {
    return null;
  }
  return { year, month, day };
}

const formatDate = (d) => `${String(d.year).padStart(4, "0")}-${pad2(d.month)}-${pad2(d.day)}`;

function today() {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1, day: now.getDate() };
}

// A time of day as {hour, minute}, from "HH:MM" (or "H:MM"), or null if
// `value` is blank or isn't one.
function parseHhmm(value) {
  const match = typeof value === "string" && /^(\d{1,2}):(\d{2})$/.exec(value);
  if (!match) return null;
  const [hour, minute] = match.slice(1).map(Number);
  return hour < 24 && minute < 60 ? { hour, minute } : null;
}

const formatTime = (t) => `${pad2(t.hour)}:${pad2(t.minute)}`;

// Parse a "time" header field (TIME_RANGE_RE's legacy "HH:MM--HH:MM TZ,
// location" convention, or anything looser) into
// {start, end, tzHint, location}.
function parseTimeField(value) {
  const text = value || "";
  const match = TIME_RANGE_RE.exec(text);
  if (!match) return { start: null, end: null, tzHint: "", location: text.trim() };
  const g = match.groups;
  return {
    start: parseHhmm(g.start),
    end: g.end ? parseHhmm(g.end) : null,
    tzHint: g.tzhint || "",
    location: g.location,
  };
}

// Whether `name` is a zone Intl recognizes -- including aliases like
// "US/Eastern" that TZ_OPTIONS doesn't list but an older header may hold.
function isValidZone(name) {
  if (!name) return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: name });
    return true;
  } catch {
    return false;
  }
}

function zoneNamePart(locale, zone, instant, style) {
  const parts = new Intl.DateTimeFormat(locale, { timeZone: zone, timeZoneName: style }).formatToParts(instant);
  return parts.find((p) => p.type === "timeZoneName").value;
}

// The UTC offset of `zone` at `instant`, in minutes.
function offsetMinutes(zone, instant) {
  const text = zoneNamePart("en-US", zone, instant, "longOffset"); // "GMT", "GMT+05:30"
  const match = /([+-])(\d{2}):(\d{2})/.exec(text);
  if (!match) return 0;
  const minutes = Number(match[2]) * 60 + Number(match[3]);
  return match[1] === "-" ? -minutes : minutes;
}

// The instant at which `zone`'s wall clock reads date/time.
function zonedInstant(zone, date, time) {
  const wall = Date.UTC(date.year, date.month - 1, date.day, time.hour, time.minute);
  // Two passes: the offset at the first guess can differ from the offset
  // at the real instant when the two straddle a DST change.
  let instant = wall - offsetMinutes(zone, new Date(wall)) * 60000;
  instant = wall - offsetMinutes(zone, new Date(instant)) * 60000;
  return new Date(instant);
}

// The abbreviation (e.g. "PDT") for IANA zone `tzName` on `refDate` at
// `refTime` (today/noon if either is null, since only the date determines
// DST for most zones) -- or `tzName` itself if it isn't a recognized zone.
// A zone with no common abbreviation gets its offset instead, in tzdata's
// own style ("+04", "+0545").
function tzAbbrev(tzName, refDate, refTime) {
  if (!isValidZone(tzName)) return tzName;
  const instant = zonedInstant(tzName, refDate || today(), refTime || { hour: 12, minute: 0 });
  for (const locale of ABBREV_LOCALES) {
    const name = zoneNamePart(locale, tzName, instant, "short");
    if (/^[A-Z]{2,5}$/.test(name)) return name;
  }
  const offset = offsetMinutes(tzName, instant);
  const abs = Math.abs(offset);
  const minutes = abs % 60 ? pad2(abs % 60) : "";
  return `${offset < 0 ? "-" : "+"}${pad2(Math.floor(abs / 60))}${minutes}`;
}

// Compose the "time" header field's string (e.g. "10:00--10:30 PDT") from
// the Start/End times and the Timezone field.
function composeTimeField(start, end, tzName, refDate, tzHint = "") {
  // Location isn't folded in here -- it's written to its own "location"
  // field and recombined with this one for display by
  // settings/template.tex's \cnHdrTimeLine.
  let timePart = "";
  if (start && end) timePart = `${formatTime(start)}--${formatTime(end)}`;
  else if (start) timePart = formatTime(start);

  // A real zone pick always wins over a hint carried from the last load
  // (see parseTimeField) -- once the user actually chooses a zone, the
  // hint's job (preventing round-trip data loss) is done.
  const abbrev = tzName ? tzAbbrev(tzName, refDate, start) : tzHint;
  if (abbrev) timePart = `${timePart} ${abbrev}`.trim();
  return timePart;
}

// The header form's initial values for stored header `fields` (an object
// covering every name in pipeline.js's HEADER_FIELDS).
function formFromHeader(fields, todayDate = null) {
  const { start, end, tzHint, location } = parseTimeField(fields.time);
  const date = parseIsoDate(fields.date) || todayDate || today();
  return {
    topic: fields.topic,
    // fields.location is what the Location field wrote on a previous save;
    // an entry that predates that field falls back to whatever's parsed
    // out of the "time" text.
    location: fields.location || location,
    // A file with no date yet (freshly created) starts the picker on today
    // rather than blank -- the renderer saves the form right after loading
    // it, so this also becomes the stored value.
    date: formatDate(date),
    start: start ? formatTime(start) : "",
    end: end ? formatTime(end) : "",
    // fields.timezone is the IANA zone name the picker wrote on a previous
    // save; an entry that predates that field, or one hand-edited to
    // something no longer a valid zone, falls back to unset -- the
    // abbreviation in tz_hint still shows through then.
    timezone: isValidZone(fields.timezone) ? fields.timezone : "",
    tz_hint: tzHint,
    attendees: fields.attendees,
  };
}

// The stored header fields (every name in pipeline.js's HEADER_FIELDS) for
// header form values `form`, as sent by the renderer. Missing or
// non-string values are treated as blank, and an unrecognized timezone or
// malformed date/time as unset.
function headerFromForm(form) {
  const values = Object.fromEntries(
    FORM_FIELDS.map((name) => [name, typeof form[name] === "string" ? form[name] : ""])
  );
  const refDate = parseIsoDate(values.date);
  const tzName = isValidZone(values.timezone) ? values.timezone : "";
  return {
    topic: values.topic,
    date: refDate ? formatDate(refDate) : "",
    attendees: values.attendees,
    time: composeTimeField(parseHhmm(values.start), parseHhmm(values.end), tzName, refDate, values.tz_hint),
    // The picker's actual IANA zone name (distinct from the abbreviation
    // baked into "time" above), so the exact zone can be restored next
    // time this file is opened.
    timezone: tzName,
    location: values.location,
  };
}

module.exports = {
  TZ_OPTIONS,
  FORM_FIELDS,
  parseIsoDate,
  parseHhmm,
  parseTimeField,
  tzAbbrev,
  composeTimeField,
  formFromHeader,
  headerFromForm,
};
