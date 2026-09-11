"""Streamlit front end for the Cornell notes pipeline: edit the header and a
markdown file, render, and preview the resulting PDF -- all without leaving
the browser. Run with `make app` (see ../Makefile) or directly:

    streamlit run app/streamlit_app.py
"""
import base64
import datetime
import re
import shutil
import uuid
import zoneinfo
from pathlib import Path

import streamlit as st

import pipeline
from components.code_editor import code_editor

st.set_page_config(page_title="Markdown Cornell Notes", layout="wide")

# Shared by both panes so their bottoms line up, not just their tops (which
# already match since both start with a single caption line -- see
# _render_pdf_pane and the Markdown pane's st.caption in main()). Deliberately
# shorter than a full-width, letter-size page (aspect ratio 11/8.5 ~= 1.29 --
# see settings/page.yaml's `paper`) fits at the ~775px a half-width column
# comes out to in a typical wide-layout browser window (775 * 1.29 ~= 1000),
# so both panes fit more comfortably on screen; the PDF frame still fills its
# full width via #view=FitH (see _render_pdf_pane) regardless of column
# width, just with some scrolling needed to see the bottom of the page.
# This is the "100%" value of the pane-height dropdown in the button row --
# see PANE_HEIGHT_OPTIONS and _pane_height().
BASE_PANE_HEIGHT = 600

# Offered in the button row so the editor/PDF panes can be shrunk (e.g. on a
# smaller screen) or grown beyond BASE_PANE_HEIGHT's default.
PANE_HEIGHT_OPTIONS = ["30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}

DATE_FORMAT = "%Y-%m-%d"

# "" first so the timezone picker can start unset, same as a blank date/time.
# "Factory" is a tzdata placeholder, not a real zone -- not useful to offer.
TZ_OPTIONS = [""] + sorted(z for z in zoneinfo.available_timezones() if z != "Factory")

# Recognizes the legacy "time" field convention "HH:MM--HH:MM TZ, location"
# (also accepting a single "-"/en dash, or "to" for the range) -- from
# before "timezone"/"location" were their own fields, when this app baked
# both into "time" (e.g. "10:00--10:30 EDT, Teams"). Only used as a
# fallback in _ensure_header_loaded, for values not covered by those
# fields (hand-edited entries, or ones written before they existed), so
# such entries still show their start/end/location correctly on first
# load. An abbreviation like "EDT" doesn't map back to one specific IANA
# zone, so it's kept as tzhint (passed through as-is by
# _compose_time_field) rather than resolved to a real zone in the dropdown.
TIME_RANGE_RE = re.compile(
    r"^\s*(?P<start>\d{1,2}:\d{2})"
    r"(?:\s*(?:--|-|–|to)\s*(?P<end>\d{1,2}:\d{2}))?"
    r"(?:\s+(?P<tzhint>[A-Z]{2,6}))?"
    r"\s*,?\s*(?P<location>.*?)\s*$"
)


def _header_field_key(filename, name):
    """The st.session_state key holding filename's `name` header field
    (one of pipeline.HEADER_FIELDS)."""
    return f"header__{filename}__{name}"


def _date_picker_key(filename):
    """The st.session_state key for filename's Date picker widget.

    st.date_input's widget state is a datetime.date (or None), not the
    "YYYY-MM-DD" string the yaml file and _current_header_fields() need
    -- so the picker gets its own key, synced into the string-valued
    header_field_key("date") after every render (see _render_header_fields).
    """
    return _header_field_key(filename, "date") + "__picker"


def _parse_iso_date(value):
    """Parse a "YYYY-MM-DD" string into a datetime.date, or None if
    `value` isn't one.
    """
    try:
        return datetime.datetime.strptime(value, DATE_FORMAT).date()
    except (TypeError, ValueError):
        return None


def _time_field_keys(filename):
    """The st.session_state keys for filename's Start/End/Timezone
    widgets, and its parsed timezone-hint/location text.

    Same reasoning as _date_picker_key: the widgets' own state (times, a
    zone name, free text) isn't the "time" field's string, so each piece
    gets its own key, composed into header_field_key("time") after every
    render (see _render_header_fields / _compose_time_field).
    """
    base = _header_field_key(filename, "time")
    return {
        "start": f"{base}__start",
        "end": f"{base}__end",
        "tz": f"{base}__tz",
        "tz_hint": f"{base}__tz_hint",
        "location": f"{base}__location",
    }


def _parse_time_field(value):
    """Parse a "time" header field (TIME_RANGE_RE's legacy
    "HH:MM--HH:MM TZ, location" convention, or anything looser) into
    (start, end, tz_hint, location) -- start/end as datetime.time (or
    None), tz_hint/location as strings.
    """
    match = TIME_RANGE_RE.match(value or "")
    if not match:
        return None, None, "", (value or "").strip()

    def to_time(s):
        """Parse an "HH:MM" string into a datetime.time, or None if blank."""
        return datetime.datetime.strptime(s, "%H:%M").time() if s else None

    return (
        to_time(match.group("start")),
        to_time(match.group("end")),
        match.group("tzhint") or "",
        match.group("location"),
    )


def _tz_abbrev(tz_name, ref_date, ref_time):
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


def _compose_time_field(start, end, tz_name, ref_date, tz_hint=""):
    """Compose the "time" header field's string (e.g. "10:00--10:30 PDT")
    from the Start/End time widgets and the timezone dropdown (see
    _render_header_fields).
    """
    # Location is no longer folded in here -- it's written to its own
    # "location" field (see _render_header_fields) and recombined with
    # this field for display by settings/template.tex's \cnHdrTimeLine.
    if start and end:
        time_part = f"{start.strftime('%H:%M')}--{end.strftime('%H:%M')}"
    elif start:
        time_part = start.strftime("%H:%M")
    else:
        time_part = ""

    # A real dropdown pick always wins over a hint carried from the last
    # load (see _parse_time_field) -- once the user actually chooses a
    # zone, the hint's job (preventing round-trip data loss) is done.
    abbrev = _tz_abbrev(tz_name, ref_date, start) if tz_name else tz_hint
    if abbrev:
        time_part = f"{time_part} {abbrev}".strip()

    return time_part


def _ensure_header_loaded(filename):
    """Populate st.session_state with filename's header fields and widget
    state (date, time, timezone, location) the first time filename is
    used this session, so the widgets in _render_header_fields have
    something to bind to. A no-op on later calls, once already loaded.
    """
    probe_key = _header_field_key(filename, pipeline.HEADER_FIELDS[0])
    if probe_key not in st.session_state:
        fields = pipeline.read_header(filename)
        for name in pipeline.HEADER_FIELDS:
            st.session_state[_header_field_key(filename, name)] = fields[name]
        # A file with no date yet (freshly created) starts the picker on
        # today rather than blank -- _render_header_fields writes whatever
        # the picker holds back into the "date" field on every run, so this
        # also becomes the saved value the first time the file is rendered.
        st.session_state[_date_picker_key(filename)] = (
            _parse_iso_date(fields["date"]) or datetime.date.today()
        )

        start, end, tz_hint, location = _parse_time_field(fields["time"])
        time_keys = _time_field_keys(filename)
        st.session_state[time_keys["start"]] = start
        st.session_state[time_keys["end"]] = end
        # fields["timezone"] is the IANA zone name the dropdown wrote on a
        # previous save (see _render_header_fields); an entry that predates
        # this field, or one hand-edited to something no longer a valid
        # zone, falls back to unset -- the abbreviation in tz_hint (parsed
        # from the "time" text above) still shows through in that case.
        tz_value = fields["timezone"] if fields["timezone"] in TZ_OPTIONS else ""
        st.session_state[time_keys["tz"]] = tz_value
        st.session_state[time_keys["tz_hint"]] = tz_hint
        # fields["location"] is what the Location field wrote on a previous
        # save (see _render_header_fields); an entry that predates this
        # field falls back to whatever's parsed out of the "time" text.
        st.session_state[time_keys["location"]] = fields["location"] or location


@st.cache_resource
def _prune_stale_build_dirs():
    """Remove any build/app-<id> directories left over from a previous
    run of the app (see _do_render's per-session BUILDDIR).

    st.cache_resource caches across every session of this server process,
    so this body runs exactly once, on whichever session calls it first --
    before any session has had a chance to create its own build/app-<id>.
    Anything matching app-* found here must be left over from a
    *previous* run of the app (the process was restarted, e.g. `make
    app` re-run after a crash or a plain Ctrl-C), since otherwise nothing
    would have created it yet.
    """
    build_root = pipeline.PROJECT_ROOT / "build"
    if not build_root.is_dir():
        return
    for child in build_root.iterdir():
        if child.is_dir() and child.name.startswith("app-"):
            shutil.rmtree(child, ignore_errors=True)


def _init_state():
    """Initialize every st.session_state key this app relies on, the
    first time each is needed (via setdefault, or an explicit "not in"
    check where the initial value takes some computing) -- safe to call
    on every rerun.
    """
    if "selected_file" not in st.session_state:
        files = pipeline.list_markdown_files()
        st.session_state.selected_file = files[0] if files else None

    st.session_state.setdefault("drafts", {})
    st.session_state.setdefault("last_saved", {})
    st.session_state.setdefault("rendered_snapshot", {})
    st.session_state.setdefault("pdf_bytes", None)
    st.session_state.setdefault("pdf_name", None)
    st.session_state.setdefault("build_ok", None)
    st.session_state.setdefault("build_log", "")
    st.session_state.setdefault("confirm_delete", False)
    st.session_state.setdefault("flush_token", 0)
    st.session_state.setdefault("pending_render", False)
    st.session_state.setdefault("render_awaiting_reply", False)
    st.session_state.setdefault("asset_uploader_version", 0)
    st.session_state.setdefault("asset_current_dir", "")
    st.session_state.setdefault("asset_folder_input_version", 0)
    st.session_state.setdefault("checked_existing_pdf", set())
    st.session_state.setdefault("pane_height_pct", "100%")
    # Keys a per-session BUILDDIR (see _do_render) so two sessions rendering
    # around the same time never race on the same scratch directory.
    st.session_state.setdefault("build_id", uuid.uuid4().hex)

    # Opportunistically show a PDF that already exists on disk for the
    # selected file's header, so there's something in the right pane before
    # the user has clicked Render at all. Only worth checking once per file
    # per session -- topic_slug() shells out to a subprocess, and if no PDF
    # exists yet, nothing changes that fact until an actual Render (which
    # sets pdf_bytes directly in _do_render(), bypassing this check anyway).
    filename = st.session_state.selected_file
    if (
        st.session_state.pdf_bytes is None
        and filename
        and filename not in st.session_state.checked_existing_pdf
    ):
        st.session_state.checked_existing_pdf.add(filename)
        try:
            yaml_path = pipeline.yaml_path_for(filename)
            slug = pipeline.topic_slug(yaml_path)
            existing = pipeline.PDF_DIR / f"{slug}.pdf"
            if existing.exists():
                st.session_state.pdf_bytes = existing.read_bytes()
                st.session_state.pdf_name = existing.name
        except pipeline.PipelineError:
            pass


def _current_header_fields(filename):
    """filename's current header fields, read back out of
    st.session_state (see _header_field_key), as a dict covering every
    name in pipeline.HEADER_FIELDS.
    """
    return {
        name: st.session_state[_header_field_key(filename, name)]
        for name in pipeline.HEADER_FIELDS
    }


def _draft_for(filename):
    """filename's current (possibly unsaved) markdown content, loading it
    from disk into st.session_state.drafts the first time filename is
    used this session.
    """
    if filename not in st.session_state.drafts:
        st.session_state.drafts[filename] = pipeline.read_markdown_file(filename)
    return st.session_state.drafts[filename]


def _autosave(filename):
    """Write filename's header/markdown to disk whenever either has
    changed since the last write, returning whether the save succeeded.

    Previously a disk write only happened on Render, so a closed tab or
    crashed session between renders lost whatever had been typed.
    last_saved's snapshot lets this run every rerun (main() calls it
    after every keystroke-triggered header update and every editor sync)
    without rewriting identical content each time.

    A write failure (permissions, disk full) is caught rather than left
    to crash the whole script run with a traceback -- previously a disk
    write only happened on an explicit Render click, so such a failure
    was rare and isolated; now that this runs on nearly every rerun, an
    uncaught one would repeat on almost every keystroke instead.
    last_saved is deliberately not updated on failure, so the next rerun
    retries the same save.
    """
    if not filename:
        return True
    header_fields = _current_header_fields(filename)
    markdown_value = st.session_state.drafts.get(filename, "")
    snapshot = (tuple(header_fields.items()), markdown_value)
    if st.session_state.last_saved.get(filename) == snapshot:
        return True
    try:
        pipeline.write_header(filename, header_fields)
        pipeline.write_markdown_file(filename, markdown_value)
    except OSError as exc:
        st.warning(f"Couldn't autosave {filename}: {exc}")
        return False
    st.session_state.last_saved[filename] = snapshot
    return True


def _render_header_fields(filename, files):
    """Render the collapsible Header section (Topic/Location, Date/
    Start/End/Timezone, Attendees/markdown-file picker) for filename, and
    write the composed "time"/"timezone"/"location" fields back to
    st.session_state from the widgets' current values.
    """
    time_keys = _time_field_keys(filename)

    with st.expander("Header", expanded=True):
        topic_col, date_col, attendees_col = st.columns(3)
        with topic_col, st.container(gap="xsmall"):
            st.text_input("Topic", key=_header_field_key(filename, "topic"))
            st.text_input("Location", key=time_keys["location"])

        with date_col, st.container(gap="xsmall"):
            picked = st.date_input(
                "Date", key=_date_picker_key(filename), format="YYYY-MM-DD"
            )
            st.session_state[_header_field_key(filename, "date")] = (
                picked.strftime(DATE_FORMAT) if picked else ""
            )

            start_col, end_col, tz_col = st.columns(3)
            start = start_col.time_input("Start", key=time_keys["start"], format="12h")
            end = end_col.time_input("End", key=time_keys["end"], format="12h")
            tz_name = tz_col.selectbox(
                "Timezone", TZ_OPTIONS, key=time_keys["tz"], format_func=lambda z: z or "(none)"
            )

        with attendees_col, st.container(gap="xsmall"):
            st.text_input("Attendees", key=_header_field_key(filename, "attendees"))
            if files:
                st.selectbox(
                    "Markdown file",
                    files,
                    key="selected_file",
                    on_change=lambda: st.session_state.update(confirm_delete=False),
                )

    ref_date = _parse_iso_date(st.session_state[_header_field_key(filename, "date")])
    location = st.session_state[time_keys["location"]]
    tz_hint = st.session_state[time_keys["tz_hint"]]
    st.session_state[_header_field_key(filename, "time")] = _compose_time_field(
        start, end, tz_name, ref_date, tz_hint
    )
    # Persists the dropdown's actual IANA zone name (distinct from the
    # abbreviation baked into "time" above) so _ensure_header_loaded can
    # restore the exact zone next time this file is opened.
    st.session_state[_header_field_key(filename, "timezone")] = tz_name
    # Persists the Location field directly so _ensure_header_loaded doesn't
    # have to re-parse it back out of "time" next time this file is opened.
    st.session_state[_header_field_key(filename, "location")] = location


def _resolve_selected_file():
    """Apply any pending selection change, then make sure
    st.session_state.selected_file names a file that actually exists
    (falling back to the first available one, or None), returning the
    current list of markdown files.

    Streamlit forbids setting st.session_state[key] once that key's
    widget has been instantiated in the current run -- the selectbox in
    _render_file_controls owns "selected_file" for the rest of this run
    as soon as it's created. The create/delete handlers further down
    (which need to change the selection) run *after* that point in the
    same run, so they can't set it directly; they stash the target
    filename here instead, applied before the selectbox is instantiated
    on the rerun they trigger.
    """
    if "pending_select" in st.session_state:
        st.session_state.selected_file = st.session_state.pop("pending_select")

    files = pipeline.list_markdown_files()
    if not files:
        st.session_state.selected_file = None
    elif st.session_state.selected_file not in files:
        st.session_state.selected_file = files[0]
    return files


def _pane_height():
    """The editor/PDF pane height in pixels: BASE_PANE_HEIGHT scaled by the
    button row's pane-height dropdown (st.session_state.pane_height_pct).
    """
    percent = int(st.session_state.pane_height_pct.rstrip("%"))
    return round(BASE_PANE_HEIGHT * percent / 100)


def _render_file_controls(files):
    """Render the New file/Delete file/Render/Download PDF/pane-height
    button row.
    """
    # A render is in flight from the moment Render is clicked until
    # _do_render() finishes and reruns (see the flush-token comment below) --
    # disable actions that would race it or duplicate the click across that
    # window's two-plus reruns.
    busy = st.session_state.pending_render

    if not files:
        st.error("No markdown files in md/. Create one below.")

    # A horizontal, full-width container (children sized to their own
    # content and laid out left-to-right, unlike st.columns' equal-fraction
    # split) so New file/Delete file/Render/Download PDF sit right after
    # each other, centered as a group, with standard spacing between them.
    button_row = st.container(horizontal=True, gap="small", horizontal_alignment="center")

    with button_row:
        with st.popover("New file"):
            new_name = st.text_input(
                "File name", placeholder="my-notes", key="new_file_name", disabled=busy
            )
            if st.button("Create", key="create_file_btn", disabled=busy):
                try:
                    created = pipeline.create_markdown_file(new_name)
                    st.session_state.pending_select = created
                    st.session_state.drafts[created] = pipeline.read_markdown_file(created)
                    st.rerun()
                except pipeline.PipelineError as exc:
                    st.error(str(exc))

        if files and st.session_state.selected_file:
            if not st.session_state.confirm_delete:
                if st.button("Delete file", key="delete_file_btn", disabled=busy):
                    st.session_state.confirm_delete = True
                    st.rerun()
            else:
                with st.container(horizontal=True, gap="small"):
                    st.warning(f"Delete {st.session_state.selected_file}?")
                    if st.button("Yes, delete", key="confirm_delete_btn", disabled=busy):
                        try:
                            deleted = st.session_state.selected_file
                            pipeline.delete_markdown_file(deleted)
                            st.session_state.drafts.pop(deleted, None)
                            st.session_state.last_saved.pop(deleted, None)
                            st.session_state.rendered_snapshot.pop(deleted, None)
                            st.session_state.checked_existing_pdf.discard(deleted)
                            for name in pipeline.HEADER_FIELDS:
                                st.session_state.pop(_header_field_key(deleted, name), None)
                            st.session_state.pop(_date_picker_key(deleted), None)
                            for time_key in _time_field_keys(deleted).values():
                                st.session_state.pop(time_key, None)
                            st.session_state.confirm_delete = False
                            remaining = pipeline.list_markdown_files()
                            st.session_state.pending_select = remaining[0] if remaining else None
                            st.rerun()
                        except pipeline.PipelineError as exc:
                            st.session_state.confirm_delete = False
                            st.error(str(exc))
                    if st.button("Cancel", key="cancel_delete_btn"):
                        st.session_state.confirm_delete = False
                        st.rerun()

        # Doesn't call _do_render() directly: the editor syncs its content
        # to Python on a debounce (or on blur), so at the exact instant this
        # click is processed, st.session_state.drafts may not yet include
        # whatever was typed in the last moment before the click -- and
        # since the browser delivers our cross-frame "flush now" message
        # asynchronously, it can lose the race against this click's own
        # rerun and arrive too late to matter for this run. Bumping
        # flush_token instead asks the editor to send its current content
        # *right now*; main() waits for that reply (a guaranteed second
        # rerun, since a component's setComponentValue always triggers one)
        # before actually building, so the save is never stale.
        if st.button("Render", type="primary", key="render_btn", disabled=busy):
            st.session_state.pending_render = True
            st.session_state.render_awaiting_reply = False
            st.session_state.flush_token += 1

        if st.session_state.pdf_bytes is not None:
            st.download_button(
                "Download PDF",
                data=st.session_state.pdf_bytes,
                file_name=st.session_state.pdf_name,
                mime="application/pdf",
                key="download_pdf_btn",
                disabled=busy,
            )
        else:
            st.button("Download PDF", disabled=True, key="download_pdf_btn_disabled")

        st.selectbox(
            "Pane Height",
            PANE_HEIGHT_OPTIONS,
            key="pane_height_pct",
            width=110,
            label_visibility="collapsed",
        )


def _render_asset_breadcrumbs(current_dir):
    """Render a clickable "assets / <folder> / <subfolder>" breadcrumb
    trail for `current_dir`, letting the user jump back to any ancestor
    folder.
    """
    parts = current_dir.split("/") if current_dir else []
    cols = st.columns(len(parts) + 1)
    if cols[0].button("assets", key="asset_crumb_root", disabled=not current_dir):
        st.session_state.asset_current_dir = ""
        st.rerun()
    accumulated = ""
    for col, part in zip(cols[1:], parts):
        accumulated = f"{accumulated}/{part}" if accumulated else part
        target = accumulated
        if col.button(part, key=f"asset_crumb_{target}", disabled=(target == current_dir)):
            st.session_state.asset_current_dir = target
            st.rerun()


def _render_assets_panel():
    """Render the Assets expander's contents for the current folder:
    breadcrumbs, new-folder/upload controls, the folder/file listing
    (with rename/delete/move actions), and bulk-move for selected files.
    """
    current_dir = st.session_state.asset_current_dir
    _render_asset_breadcrumbs(current_dir)

    folder_col, folder_btn_col = st.columns([4, 1])
    new_folder_name = folder_col.text_input(
        "New folder name",
        key=f"new_asset_folder_{st.session_state.asset_folder_input_version}",
        label_visibility="collapsed",
        placeholder="New folder name",
    )
    if folder_btn_col.button("Create folder", key="create_asset_folder_btn"):
        try:
            pipeline.create_asset_folder(new_folder_name, current_dir)
        except pipeline.PipelineError as exc:
            st.error(str(exc))
        else:
            # Bumping the widget's key remounts a fresh, empty input on the
            # rerun below, the same trick used for the file uploader.
            st.session_state.asset_folder_input_version += 1
            st.rerun()

    uploaded = st.file_uploader(
        "Add files",
        accept_multiple_files=True,
        key=f"asset_uploader_{st.session_state.asset_uploader_version}",
    )
    if uploaded and st.button("Upload", key="upload_assets_btn"):
        for f in uploaded:
            try:
                pipeline.save_asset(f.name, f.getvalue(), current_dir)
            except pipeline.PipelineError as exc:
                st.error(str(exc))
        # Bumping the widget's key remounts a fresh, empty uploader on the
        # rerun below -- otherwise the same files would still be "selected"
        # and re-upload (erroring as already-existing) on every later rerun.
        st.session_state.asset_uploader_version += 1
        st.rerun()

    folders, files = pipeline.list_asset_dir(current_dir)
    if not folders and not files:
        st.caption("No folders or files here yet.")

    for name in folders:
        open_col, rename_col, delete_col = st.columns([4, 1, 1], vertical_alignment="center")
        target = f"{current_dir}/{name}" if current_dir else name
        if open_col.button(name, key=f"open_asset_folder_{target}", icon=":material/folder:"):
            st.session_state.asset_current_dir = target
            st.rerun()
        with rename_col.popover("Rename"):
            new_name = st.text_input("New name", value=name, key=f"rename_asset_folder_input_{target}")
            if st.button("Confirm", key=f"confirm_rename_asset_folder_{target}"):
                try:
                    pipeline.rename_asset_folder(name, new_name, current_dir)
                except pipeline.PipelineError as exc:
                    st.error(str(exc))
                else:
                    st.rerun()
        with delete_col.popover("Delete"):
            st.write(f"Delete folder `{name}` and everything inside it?")
            if st.button("Confirm", key=f"confirm_delete_asset_folder_{target}"):
                try:
                    pipeline.delete_asset_folder(name, current_dir)
                except pipeline.PipelineError as exc:
                    st.error(str(exc))
                st.rerun()

    def _select_key(name):
        """The st.session_state key for `name`'s bulk-move checkbox in
        the current folder."""
        return f"select_asset_{current_dir}/{name}"

    for name in files:
        path = pipeline.ASSETS_DIR / current_dir / name
        select_col, thumb_col, name_col, size_col, delete_col = st.columns(
            [0.4, 1, 4, 1.5, 1], vertical_alignment="center"
        )
        select_col.checkbox("Select", key=_select_key(name), label_visibility="collapsed")
        if Path(name).suffix.lower() in IMAGE_SUFFIXES:
            thumb_col.image(str(path), width=40)
        display_path = f"assets/{current_dir}/{name}" if current_dir else f"assets/{name}"
        name_col.code(display_path, language=None)
        size_col.caption(f"{path.stat().st_size / 1024:.1f} KB")
        with delete_col.popover("Delete"):
            st.write(f"Delete `{name}`?")
            if st.button("Confirm", key=f"confirm_delete_asset_{current_dir}/{name}"):
                try:
                    pipeline.delete_asset(name, current_dir)
                except pipeline.PipelineError as exc:
                    st.error(str(exc))
                st.rerun()

    selected_files = [name for name in files if st.session_state.get(_select_key(name))]
    if selected_files:
        dest_options = [p for p in pipeline.list_asset_folder_paths() if p != current_dir]
        if dest_options:
            move_col, move_btn_col = st.columns([4, 1])
            dest = move_col.selectbox(
                "Move to",
                options=dest_options,
                format_func=lambda p: f"assets/{p}" if p else "assets",
                key=f"move_asset_dest_{current_dir}",
                label_visibility="collapsed",
            )
            if move_btn_col.button(f"Move {len(selected_files)} selected", key="move_assets_btn"):
                errors = []
                for name in selected_files:
                    try:
                        pipeline.move_asset(name, current_dir, dest)
                    except pipeline.PipelineError as exc:
                        errors.append(str(exc))
                    else:
                        st.session_state.pop(_select_key(name), None)
                for err in errors:
                    st.error(err)
                st.rerun()
        else:
            st.caption("Create another folder to move the selected files into.")


def _do_render():
    """Autosave, validate, and build the selected file's PDF via
    pipeline.render(), updating st.session_state's build/PDF/preview
    status. A no-op (with an error/skip message) if there's no selected
    file, autosave fails, or Topic/Date are empty.
    """
    filename = st.session_state.selected_file
    if not filename:
        st.error("No markdown file selected.")
        return

    if not _autosave(filename):
        st.session_state.build_ok = False
        st.session_state.build_log = "Render skipped: couldn't save changes to disk."
        return

    header_fields = _current_header_fields(filename)
    missing = [name for name in ("topic", "date") if not header_fields.get(name, "").strip()]
    if missing:
        st.session_state.build_ok = False
        st.session_state.build_log = (
            f"Render skipped: {' and '.join(missing)} field(s) empty.\n"
            "Fill in the header before rendering, or the output PDF's name "
            "and header row will end up mostly blank."
        )
        return

    with st.spinner("Rendering PDF..."):
        # A per-session BUILDDIR (see pipeline.render) so two sessions
        # rendering around the same time never race on the same scratch
        # directory.
        success, log, pdf_path = pipeline.render(
            filename, builddir=f"build/app-{st.session_state.build_id}"
        )

    st.session_state.build_ok = success
    st.session_state.build_log = log
    if pdf_path is not None:
        st.session_state.pdf_bytes = pdf_path.read_bytes()
        st.session_state.pdf_name = pdf_path.name
    if success:
        # Recorded so _is_preview_stale can tell whether the PDF pane still
        # reflects the header/markdown as they stood at this render, or the
        # user has since changed something.
        st.session_state.rendered_snapshot[filename] = (
            tuple(header_fields.items()),
            st.session_state.drafts.get(filename, ""),
        )


def _is_preview_stale(filename):
    """Whether the PDF pane's current content no longer reflects
    filename's header/markdown -- either because they've changed since
    the last successful render, or filename has never been rendered this
    session. False whenever there's no PDF to compare against yet.
    """
    if not filename or st.session_state.pdf_bytes is None:
        return False
    current_snapshot = (
        tuple(_current_header_fields(filename).items()),
        st.session_state.drafts.get(filename, ""),
    )
    return st.session_state.rendered_snapshot.get(filename) != current_snapshot


def _render_pdf_pane():
    """Render the right-hand PDF pane: a filename caption plus the
    current PDF (as a data-URI iframe), or a placeholder if there's no
    PDF yet.
    """
    if st.session_state.pdf_bytes is None:
        st.info("No PDF yet -- click Render.")
        return
    b64 = base64.b64encode(st.session_state.pdf_bytes).decode()
    st.caption(st.session_state.pdf_name)
    # st.markdown(unsafe_allow_html=True) injects straight into Streamlit's
    # own (unsandboxed) page DOM, unlike st.components.v1.html/iframe, which
    # always wraps its content in a *sandboxed* iframe. Chromium refuses to
    # hand data: PDFs to its built-in viewer inside a sandboxed frame (even
    # one that grants allow-scripts/allow-same-origin) -- nesting our PDF
    # iframe inside that sandboxed wrapper renders a broken-file icon
    # instead of the PDF, confirmed by hand against a real browser. A single
    # unsandboxed iframe at the top level doesn't hit that restriction.
    # The #view=FitH open parameter (honored by Chromium's built-in PDF
    # viewer) tells it to scale the page to the frame's *width* on load,
    # rather than picking its own default zoom. Plain Fit (fit both width
    # and height) was tried first, but whenever the frame was proportionally
    # wider than the page it picked height as the binding constraint,
    # letterboxing the page down narrower than the frame instead of filling
    # it -- FitH always fills the frame's width, at the cost of a vertical
    # scrollbar inside the frame if the pane height is shorter than a
    # full-width page (see BASE_PANE_HEIGHT's own comment).
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}#view=FitH" '
        f'width="100%" height="{_pane_height()}" style="border:none;"></iframe>',
        unsafe_allow_html=True,
    )


def main():
    """Entry point: lay out the whole page (title/status, Header
    expander, file controls, editor/PDF panes, Assets expander) for the
    currently selected file, driving a render when one's been requested.
    """
    if not pipeline.project_initialized():
        st.title("Markdown Cornell Notes")
        st.error(
            f"No project found in `{pipeline.PROJECT_ROOT}`. Run "
            "`markdown-cornell-notes init` (or `make init`) in that directory, "
            "then restart this app from there."
        )
        st.stop()
    _prune_stale_build_dirs()
    _init_state()
    files = _resolve_selected_file()
    if st.session_state.selected_file:
        _ensure_header_loaded(st.session_state.selected_file)

    # Streamlit's default block container reserves ~6rem of top padding to
    # clear the fixed-position toolbar header, which this single-page app
    # doesn't use. Just shrinking that padding (without also hiding the
    # header) would leave the header's fixed overlay covering the same
    # space, clipping the top of whatever now renders there -- so the
    # header itself is hidden here too.
    st.markdown(
        "<style>"
        '[data-testid="stHeader"]{display:none;}'
        ".block-container{padding-top:1rem;}"
        "</style>",
        unsafe_allow_html=True,
    )
    # Centered so the build status (appended right after the title once a
    # render has happened) reads as part of the same header line rather than
    # a separate banner further down the page.
    with st.container(horizontal=True, gap="small", horizontal_alignment="center", vertical_alignment="center"):
        st.title("Markdown Cornell Notes")
        if st.session_state.build_ok is not None:
            (st.success if st.session_state.build_ok else st.error)(
                "Build succeeded." if st.session_state.build_ok else "Build failed."
            )
        if _is_preview_stale(st.session_state.selected_file):
            st.caption(":material/warning: Preview may be out of date")

    if st.session_state.build_ok is False and st.session_state.build_log:
        with st.expander("Build log", expanded=True):
            st.code(st.session_state.build_log, language=None)

    # A tighter gap than the default between every top-level element below --
    # this is a dense, single-page app (editor/PDF panes plus everything
    # else) rather than a series of loosely related sections.
    with st.container(gap="small"):
        if st.session_state.selected_file:
            _render_header_fields(st.session_state.selected_file, files)

        _render_file_controls(files)

        # Computed once and reused below (for the editor's autocomplete list
        # and the Assets expander's file-count label) rather than walking
        # assets/ from disk twice every rerun.
        asset_files = pipeline.list_asset_files()

        if st.session_state.selected_file:
            left, right = st.columns(2)
            with left:
                st.caption(st.session_state.selected_file)
                value = code_editor(
                    value=_draft_for(st.session_state.selected_file),
                    key=st.session_state.selected_file,
                    height=_pane_height(),
                    flush_token=st.session_state.flush_token,
                    assets=asset_files,
                )
                st.session_state.drafts[st.session_state.selected_file] = value
                _autosave(st.session_state.selected_file)

                if st.session_state.pending_render:
                    if st.session_state.render_awaiting_reply:
                        # This run was triggered by the editor's reply to our
                        # flush request (or, in the unlikely case that reply
                        # never arrives, some later unrelated widget update --
                        # either way code_editor() above just returned the
                        # freshest value Streamlit has for this file, so it's
                        # safe to save and build now).
                        st.session_state.pending_render = False
                        st.session_state.render_awaiting_reply = False
                        _do_render()
                        st.rerun()  # so the build-log/success banner (rendered
                        # earlier in this same script, before _do_render() set
                        # it) actually shows up
                    else:
                        # First pass after the click: the code_editor() call
                        # just above sent the bumped flush_token, so the
                        # frontend now knows to reply -- wait for that reply's
                        # rerun before building.
                        st.session_state.render_awaiting_reply = True
            with right:
                _render_pdf_pane()

        with st.expander(f"Assets ({len(asset_files)})"):
            _render_assets_panel()


if __name__ == "__main__":
    main()
