"""Streamlit front end for the Cornell notes pipeline: edit the header and a
markdown file, render, and preview the resulting PDF -- all without leaving
the browser. Run with `make app` (see ../Makefile) or directly:

    streamlit run app/streamlit_app.py
"""
import base64
import datetime
import re
import zoneinfo
from pathlib import Path

import streamlit as st

import pipeline
from components.code_editor import code_editor

st.set_page_config(page_title="Markdown Cornell Notes", layout="wide")

# Shared by both panes so their bottoms line up, not just their tops (which
# already match since both start with a single caption line -- see
# _render_pdf_pane and the Markdown pane's st.caption in main()). Tall
# enough that a full-width, letter-size page (aspect ratio 11/8.5 ~= 1.29 --
# see settings/page.yaml's `paper`) fits without an inner scrollbar at the
# ~775px a half-width column comes out to in a typical wide-layout browser
# window (775 * 1.29 ~= 1000); a narrower window's column still fills the
# frame's width via #view=FitH (see _render_pdf_pane), just with some
# scrolling needed to see the bottom of the page.
PANE_HEIGHT = 1000

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
    return f"header__{filename}__{name}"


def _date_picker_key(filename):
    # st.date_input's widget state is a datetime.date (or None), not the
    # "YYYY-MM-DD" string the yaml file and _current_header_fields() need
    # -- so the picker gets its own key, synced into the string-valued
    # header_field_key("date") after every render (see _render_header_fields).
    return _header_field_key(filename, "date") + "__picker"


def _parse_iso_date(value):
    try:
        return datetime.datetime.strptime(value, DATE_FORMAT).date()
    except (TypeError, ValueError):
        return None


def _time_field_keys(filename):
    # Same reasoning as _date_picker_key: the widgets' own state (times, a
    # zone name, free text) isn't the "time" field's string, so each piece
    # gets its own key, composed into header_field_key("time") after every
    # render (see _render_header_fields / _compose_time_field).
    base = _header_field_key(filename, "time")
    return {
        "start": f"{base}__start",
        "end": f"{base}__end",
        "tz": f"{base}__tz",
        "tz_hint": f"{base}__tz_hint",
        "location": f"{base}__location",
    }


def _parse_time_field(value):
    match = TIME_RANGE_RE.match(value or "")
    if not match:
        return None, None, "", (value or "").strip()

    def to_time(s):
        return datetime.datetime.strptime(s, "%H:%M").time() if s else None

    return (
        to_time(match.group("start")),
        to_time(match.group("end")),
        match.group("tzhint") or "",
        match.group("location"),
    )


def _tz_abbrev(tz_name, ref_date, ref_time):
    try:
        zone = zoneinfo.ZoneInfo(tz_name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        return tz_name
    dt = datetime.datetime.combine(
        ref_date or datetime.date.today(), ref_time or datetime.time(12, 0), tzinfo=zone
    )
    return dt.tzname() or tz_name


def _compose_time_field(start, end, tz_name, ref_date, tz_hint=""):
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
    probe_key = _header_field_key(filename, pipeline.HEADER_FIELDS[0])
    if probe_key not in st.session_state:
        fields = pipeline.read_header(filename)
        for name in pipeline.HEADER_FIELDS:
            st.session_state[_header_field_key(filename, name)] = fields[name]
        st.session_state[_date_picker_key(filename)] = _parse_iso_date(fields["date"])

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


def _init_state():
    if "selected_file" not in st.session_state:
        files = pipeline.list_markdown_files()
        st.session_state.selected_file = files[0] if files else None

    st.session_state.setdefault("drafts", {})
    st.session_state.setdefault("pdf_bytes", None)
    st.session_state.setdefault("pdf_name", None)
    st.session_state.setdefault("build_ok", None)
    st.session_state.setdefault("confirm_delete", False)
    st.session_state.setdefault("flush_token", 0)
    st.session_state.setdefault("pending_render", False)
    st.session_state.setdefault("render_awaiting_reply", False)
    st.session_state.setdefault("asset_uploader_version", 0)
    st.session_state.setdefault("asset_current_dir", "")
    st.session_state.setdefault("asset_folder_input_version", 0)

    # Opportunistically show a PDF that already exists on disk for the
    # selected file's header, so there's something in the right pane
    # before the user has clicked Render at all.
    if st.session_state.pdf_bytes is None and st.session_state.selected_file:
        try:
            yaml_path = pipeline.yaml_path_for(st.session_state.selected_file)
            slug = pipeline.topic_slug(yaml_path)
            existing = pipeline.PDF_DIR / f"{slug}.pdf"
            if existing.exists():
                st.session_state.pdf_bytes = existing.read_bytes()
                st.session_state.pdf_name = existing.name
        except pipeline.PipelineError:
            pass


def _current_header_fields(filename):
    return {
        name: st.session_state[_header_field_key(filename, name)]
        for name in pipeline.HEADER_FIELDS
    }


def _draft_for(filename):
    if filename not in st.session_state.drafts:
        st.session_state.drafts[filename] = pipeline.read_markdown_file(filename)
    return st.session_state.drafts[filename]


def _render_header_fields(filename, files):
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
    # Streamlit forbids setting st.session_state[key] once that key's widget
    # has been instantiated in the current run -- the selectbox in
    # _render_file_controls owns "selected_file" for the rest of this run as
    # soon as it's created. The create/delete handlers further down (which
    # need to change the selection) run *after* that point in the same run,
    # so they can't set it directly; they stash the target filename here
    # instead, applied before the selectbox is instantiated on the rerun
    # they trigger.
    if "pending_select" in st.session_state:
        st.session_state.selected_file = st.session_state.pop("pending_select")

    files = pipeline.list_markdown_files()
    if not files:
        st.session_state.selected_file = None
    elif st.session_state.selected_file not in files:
        st.session_state.selected_file = files[0]
    return files


def _render_file_controls(files):
    if not files:
        st.error("No markdown files in md/. Create one below.")

    # A horizontal, full-width container (children sized to their own
    # content and laid out left-to-right, unlike st.columns' equal-fraction
    # split) so New file/Delete file/Render/Download PDF sit right after
    # each other, centered as a group, with standard spacing between them.
    button_row = st.container(horizontal=True, gap="small", horizontal_alignment="center")

    with button_row:
        with st.popover("New file"):
            new_name = st.text_input("File name", placeholder="my-notes", key="new_file_name")
            if st.button("Create", key="create_file_btn"):
                try:
                    created = pipeline.create_markdown_file(new_name)
                    st.session_state.pending_select = created
                    st.session_state.drafts[created] = pipeline.read_markdown_file(created)
                    st.rerun()
                except pipeline.PipelineError as exc:
                    st.error(str(exc))

        if files and st.session_state.selected_file:
            if not st.session_state.confirm_delete:
                if st.button("Delete file", key="delete_file_btn"):
                    st.session_state.confirm_delete = True
                    st.rerun()
            else:
                with st.container(horizontal=True, gap="small"):
                    st.warning(f"Delete {st.session_state.selected_file}?")
                    if st.button("Yes, delete", key="confirm_delete_btn"):
                        try:
                            deleted = st.session_state.selected_file
                            pipeline.delete_markdown_file(deleted)
                            st.session_state.drafts.pop(deleted, None)
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
        if st.button("Render", type="primary", key="render_btn"):
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
            )
        else:
            st.button("Download PDF", disabled=True, key="download_pdf_btn_disabled")


def _render_asset_breadcrumbs(current_dir):
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
    filename = st.session_state.selected_file
    if not filename:
        st.error("No markdown file selected.")
        return

    pipeline.write_header(filename, _current_header_fields(filename))
    pipeline.write_markdown_file(filename, st.session_state.drafts.get(filename, ""))

    with st.spinner("Rendering PDF..."):
        success, _log, pdf_path = pipeline.render(filename)

    st.session_state.build_ok = success
    if pdf_path is not None:
        st.session_state.pdf_bytes = pdf_path.read_bytes()
        st.session_state.pdf_name = pdf_path.name


def _render_pdf_pane():
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
    # scrollbar inside the frame if PANE_HEIGHT is shorter than a
    # full-width page (see PANE_HEIGHT's own comment).
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}#view=FitH" '
        f'width="100%" height="{PANE_HEIGHT}" style="border:none;"></iframe>',
        unsafe_allow_html=True,
    )


def main():
    if not pipeline.project_initialized():
        st.title("Markdown Cornell Notes")
        st.error(
            f"No project found in `{pipeline.PROJECT_ROOT}`. Run "
            "`markdown-cornell-notes init` (or `make init`) in that directory, "
            "then restart this app from there."
        )
        st.stop()
    _init_state()
    files = _resolve_selected_file()
    if st.session_state.selected_file:
        _ensure_header_loaded(st.session_state.selected_file)

    # Streamlit's default block container reserves ~6rem of top padding for
    # a header that this single-page app doesn't use.
    st.markdown(
        "<style>.block-container{padding-top:2rem;}</style>",
        unsafe_allow_html=True,
    )
    st.title("Markdown Cornell Notes")
    if st.session_state.selected_file:
        _render_header_fields(st.session_state.selected_file, files)

    with st.expander(f"Assets ({len(pipeline.list_asset_files())})"):
        _render_assets_panel()

    _render_file_controls(files)

    if st.session_state.build_ok is not None:
        (st.success if st.session_state.build_ok else st.error)(
            "Build succeeded." if st.session_state.build_ok else "Build failed."
        )

    st.divider()

    if st.session_state.selected_file:
        left, right = st.columns(2)
        with left:
            st.caption(st.session_state.selected_file)
            value = code_editor(
                value=_draft_for(st.session_state.selected_file),
                key=st.session_state.selected_file,
                height=PANE_HEIGHT,
                flush_token=st.session_state.flush_token,
                assets=pipeline.list_asset_files(),
            )
            st.session_state.drafts[st.session_state.selected_file] = value

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


if __name__ == "__main__":
    main()
