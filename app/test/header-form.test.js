// Tests for lib/header-form.js: the header form <-> stored header field
// round-trip behind the editor's date/time/timezone pickers.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const hf = require("../lib/header-form");

const blankFields = (overrides = {}) => ({
  topic: "",
  date: "",
  attendees: "",
  time: "",
  timezone: "",
  location: "",
  ...overrides,
});

const t = (hour, minute = 0) => ({ hour, minute });
const d = (year, month, day) => ({ year, month, day });

test("legacy 'HH:MM--HH:MM TZ, location' time field is split back apart", () => {
  assert.deepEqual(hf.parseTimeField("10:00--10:30 EDT, Teams"), {
    start: t(10),
    end: t(10, 30),
    tzHint: "EDT",
    location: "Teams",
  });
});

test("free text that isn't a time range is kept, as location", () => {
  assert.deepEqual(hf.parseTimeField("Lunch, Room 4"), { start: null, end: null, tzHint: "", location: "Lunch, Room 4" });
});

test("zone abbreviation follows DST for the meeting's date", () => {
  assert.equal(hf.composeTimeField(t(10), t(10, 30), "America/Los_Angeles", d(2026, 7, 1)), "10:00--10:30 PDT");
  assert.equal(hf.composeTimeField(t(10), null, "America/Los_Angeles", d(2026, 1, 15)), "10:00 PST");
});

test("abbreviations come from whichever locale knows them", () => {
  assert.equal(hf.tzAbbrev("Europe/London", d(2026, 7, 1), t(12)), "BST");
  assert.equal(hf.tzAbbrev("Europe/Berlin", d(2026, 1, 15), t(12)), "CET");
  assert.equal(hf.tzAbbrev("Australia/Sydney", d(2026, 1, 15), t(12)), "AEDT");
  assert.equal(hf.tzAbbrev("Asia/Tokyo", d(2026, 1, 15), t(12)), "JST");
  assert.equal(hf.tzAbbrev("UTC", d(2026, 1, 15), t(12)), "UTC");
});

test("a zone with no abbreviation gets its offset, tzdata-style", () => {
  assert.equal(hf.tzAbbrev("America/Sao_Paulo", d(2026, 1, 15), t(12)), "-03");
  assert.equal(hf.tzAbbrev("Asia/Kathmandu", d(2026, 1, 15), t(12)), "+0545");
});

test("abbreviation uses the meeting's own time on a DST-change day", () => {
  // US DST starts 2026-03-08 at 02:00 local.
  assert.equal(hf.tzAbbrev("America/New_York", d(2026, 3, 8), t(1)), "EST");
  assert.equal(hf.tzAbbrev("America/New_York", d(2026, 3, 8), t(9)), "EDT");
});

test("a real zone pick replaces a hint carried over from load", () => {
  assert.equal(hf.composeTimeField(t(9), null, "Europe/London", d(2026, 1, 15), "EDT"), "09:00 GMT");
  assert.equal(hf.composeTimeField(t(9), null, "", null, "EDT"), "09:00 EDT");
});

test("a freshly created file's form starts on today's date", () => {
  assert.equal(hf.formFromHeader(blankFields(), d(2026, 10, 5)).date, "2026-10-05");
});

test("a pre-timezone/location entry loads with location and hint split out of 'time'", () => {
  const form = hf.formFromHeader(blankFields({ date: "2026-08-25", time: "10:00--10:30 EDT, Teams" }));
  assert.equal(form.start, "10:00");
  assert.equal(form.end, "10:30");
  assert.equal(form.tz_hint, "EDT");
  assert.equal(form.location, "Teams");
  assert.equal(form.timezone, "");
});

test("loading a saved header into the form and saving it back is lossless", () => {
  const fields = blankFields({
    topic: "Weekly Sync",
    date: "2026-08-23",
    attendees: "Lily, Amber",
    time: "10:00--10:30 EDT",
    timezone: "America/Detroit",
    location: "Zoom",
  });
  assert.deepEqual(hf.headerFromForm(hf.formFromHeader(fields)), fields);
});

test("malformed form input degrades to blank rather than throwing", () => {
  const fields = hf.headerFromForm({ topic: 5, date: "not-a-date", start: "25:99", timezone: "Mars/Base", location: null });
  assert.deepEqual(fields, blankFields());
});

test("impossible calendar dates are rejected", () => {
  assert.equal(hf.parseIsoDate("2026-02-30"), null);
  assert.deepEqual(hf.parseIsoDate("2026-2-3"), d(2026, 2, 3));
});

test("timezone options include UTC and real zones", () => {
  assert.ok(hf.TZ_OPTIONS.includes("UTC"));
  assert.ok(hf.TZ_OPTIONS.includes("America/Detroit"));
});
