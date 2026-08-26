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

    select_col, new_col, delete_col = st.columns([3, 2, 2])

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
        'width="100%" height="750" style="border:none;"></iframe>',
        unsafe_allow_html=True,
    )


def main():
    _init_state()

    st.title("Cornell Notes")
    _render_header_fields()
    st.divider()
    _render_file_controls()

    if st.button("Render", type="primary", key="render_btn"):
        _do_render()

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
            value = code_editor(
                value=_draft_for(st.session_state.selected_file),
                key=st.session_state.selected_file,
                height=700,
            )
            st.session_state.drafts[st.session_state.selected_file] = value
        with right:
            st.subheader("PDF")
            _render_pdf_pane()


if __name__ == "__main__":
    main()
