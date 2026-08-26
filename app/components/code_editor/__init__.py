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


def code_editor(value: str, key: str, height: int = 700) -> str:
    """Render the markdown/HTML/LaTeX-aware editor and return its current content.

    `key` is used both as the Streamlit widget key (Streamlit's
    declare_component wrapper reserves that kwarg for its own bookkeeping
    and does not forward it to the frontend) and, passed through separately
    as `doc_id`, as the file-identity signal the frontend uses to decide
    whether to reload its document -- see the cursor-clobber guard in
    editor.js. Pass the selected filename.
    """
    return _component_func(value=value, doc_id=key, height=height, key=key, default=value)
