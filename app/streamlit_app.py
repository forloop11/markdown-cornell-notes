"""Streamlit front end for the Cornell notes pipeline: edit the header and a
markdown file, render, and preview the resulting PDF -- all without leaving
the browser. Run with `make app` (see ../Makefile) or directly:

    streamlit run app/streamlit_app.py
"""
import base64

import streamlit as st

import pipeline
from components.code_editor import code_editor

st.set_page_config(page_title="Cornell Notes", layout="wide")

# Shared by both panes so their bottoms line up, not just their tops (which
# already match since both start with a single caption line -- see
# _render_pdf_pane and the Markdown pane's st.caption in main()).
PANE_HEIGHT = 700


def _init_state():
    if "header_loaded" not in st.session_state:
        fields = pipeline.read_header()
        for name in pipeline.HEADER_FIELDS:
            st.session_state[f"header_{name}"] = fields[name]
        st.session_state.header_loaded = True

    if "selected_file" not in st.session_state:
        files = pipeline.list_markdown_files()
        st.session_state.selected_file = files[0] if files else None

    st.session_state.setdefault("drafts", {})
    st.session_state.setdefault("pdf_bytes", None)
    st.session_state.setdefault("pdf_name", None)
    st.session_state.setdefault("build_log", None)
    st.session_state.setdefault("build_ok", None)
    st.session_state.setdefault("confirm_delete", False)
    st.session_state.setdefault("flush_token", 0)
    st.session_state.setdefault("pending_render", False)
    st.session_state.setdefault("render_awaiting_reply", False)

    # Opportunistically show a PDF that already exists on disk for the
    # current header, so there's something in the right pane before the
    # user has clicked Render at all.
    if st.session_state.pdf_bytes is None:
        try:
            slug = pipeline.topic_slug()
            existing = pipeline.PDF_DIR / f"{slug}.pdf"
            if existing.exists():
                st.session_state.pdf_bytes = existing.read_bytes()
                st.session_state.pdf_name = existing.name
        except pipeline.PipelineError:
            pass


def _current_header_fields():
    return {name: st.session_state[f"header_{name}"] for name in pipeline.HEADER_FIELDS}


def _draft_for(filename):
    if filename not in st.session_state.drafts:
        st.session_state.drafts[filename] = pipeline.read_markdown_file(filename)
    return st.session_state.drafts[filename]


def _render_header_fields():
    st.subheader("Header")
    cols = st.columns(4)
    labels = {"topic": "Topic", "date": "Date", "attendees": "Attendees", "time": "Time"}
    for col, name in zip(cols, pipeline.HEADER_FIELDS):
        col.text_input(labels[name], key=f"header_{name}")


def _render_file_controls():
    # Streamlit forbids setting st.session_state[key] once that key's widget
    # has been instantiated in the current run -- the selectbox below owns
    # "selected_file" for the rest of this run as soon as it's created. The
    # create/delete handlers further down (which need to change the
    # selection) run *after* that point in the same run, so they can't set
    # it directly; they stash the target filename here instead, applied
    # before the selectbox is instantiated on the rerun they trigger.
    if "pending_select" in st.session_state:
        st.session_state.selected_file = st.session_state.pop("pending_select")

    files = pipeline.list_markdown_files()
    if not files:
        st.error("No markdown files in md/. Create one below.")
        st.session_state.selected_file = None
    elif st.session_state.selected_file not in files:
        st.session_state.selected_file = files[0]

    # The spacer column pushes Render/Download to the right edge of the row.
    select_col, new_col, delete_col, _spacer_col, render_col, download_col = st.columns(
        [3, 1.2, 1.2, 2.2, 1.2, 1.6]
    )

    with select_col:
        if files:
            st.selectbox(
                "Markdown file",
                files,
                key="selected_file",
                on_change=lambda: st.session_state.update(confirm_delete=False),
            )

    with new_col:
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

    with delete_col:
        if files and st.session_state.selected_file:
            if not st.session_state.confirm_delete:
                if st.button("Delete file", key="delete_file_btn"):
                    st.session_state.confirm_delete = True
                    st.rerun()
            else:
                st.warning(f"Delete {st.session_state.selected_file}?")
                yes_col, no_col = st.columns(2)
                if yes_col.button("Yes, delete", key="confirm_delete_btn"):
                    try:
                        pipeline.delete_markdown_file(st.session_state.selected_file)
                        st.session_state.drafts.pop(st.session_state.selected_file, None)
                        st.session_state.confirm_delete = False
                        remaining = pipeline.list_markdown_files()
                        st.session_state.pending_select = remaining[0] if remaining else None
                        st.rerun()
                    except pipeline.PipelineError as exc:
                        st.session_state.confirm_delete = False
                        st.error(str(exc))
                if no_col.button("Cancel", key="cancel_delete_btn"):
                    st.session_state.confirm_delete = False
                    st.rerun()

    with render_col:
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

    with download_col:
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


def _do_render():
    filename = st.session_state.selected_file
    if not filename:
        st.error("No markdown file selected.")
        return

    pipeline.write_header(_current_header_fields())
    pipeline.write_markdown_file(filename, st.session_state.drafts.get(filename, ""))

    with st.spinner("Rendering PDF..."):
        success, log, pdf_path = pipeline.render(filename)

    st.session_state.build_ok = success
    st.session_state.build_log = log
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
    st.markdown(
        f'<iframe src="data:application/pdf;base64,{b64}" '
        f'width="100%" height="{PANE_HEIGHT}" style="border:none;"></iframe>',
        unsafe_allow_html=True,
    )


def main():
    _init_state()

    st.title("Cornell Notes")
    _render_header_fields()
    st.divider()
    _render_file_controls()

    if st.session_state.build_log is not None:
        (st.success if st.session_state.build_ok else st.error)(
            "Build succeeded." if st.session_state.build_ok else "Build failed."
        )
        with st.expander("Build log", expanded=not st.session_state.build_ok):
            st.code(st.session_state.build_log or "(empty)", language="text")

    st.divider()

    if st.session_state.selected_file:
        left, right = st.columns(2)
        with left:
            st.subheader("Markdown")
            # Matches the PDF pane's st.caption(pdf_name) line so both
            # panes' iframes start at the same height -- without this, the
            # PDF pane's extra caption line pushes it down relative to the
            # editor, which otherwise goes straight from subheader to iframe.
            st.caption(st.session_state.selected_file)
            value = code_editor(
                value=_draft_for(st.session_state.selected_file),
                key=st.session_state.selected_file,
                height=PANE_HEIGHT,
                flush_token=st.session_state.flush_token,
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
            st.subheader("PDF")
            _render_pdf_pane()


if __name__ == "__main__":
    main()
