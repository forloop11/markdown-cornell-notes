"""Streamlit component wrapping a CodeMirror 6 editor (see frontend_src/editor.js).

Built as a hand-rolled component (plain postMessage protocol, no
streamlit-component-lib/React) so it needed nothing beyond esbuild to
vendor. `frontend/bundle.js` is the built artifact; rebuild it after editing
frontend_src/editor.js with:

    cd app/components/code_editor/frontend_src && npm install && npm run build
"""
import os

import streamlit.components.v1 as components

_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

_component_func = components.declare_component("code_editor", path=_FRONTEND_DIR)


def code_editor(
    value: str, key: str, height: int = 700, flush_token: int = 0, assets: list[str] | None = None
) -> str:
    """Render the markdown/HTML/LaTeX-aware editor and return its current content.

    `key` is used both as the Streamlit widget key (Streamlit's
    declare_component wrapper reserves that kwarg for its own bookkeeping
    and does not forward it to the frontend) and, passed through separately
    as `doc_id`, as the file-identity signal the frontend uses to decide
    whether to reload its document -- see the cursor-clobber guard in
    editor.js. Pass the selected filename.

    `flush_token`: bump this (e.g. an incrementing counter) to force the
    frontend to immediately send its current content back, regardless of
    the normal debounce/blur sync. See the Render button's handler in
    streamlit_app.py for why this exists and how to wait for the reply.

    `assets`: filenames from assets/ (e.g. pipeline.list_asset_files()),
    offered by the frontend's link/image-path autocompletion. Optional --
    an empty/missing list just means that completion source has nothing
    to suggest.
    """
    return _component_func(
        value=value,
        doc_id=key,
        height=height,
        flush_token=flush_token,
        assets=assets or [],
        key=key,
        default=value,
    )
