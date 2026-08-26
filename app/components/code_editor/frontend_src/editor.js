// CodeMirror 6 editor for the Cornell notes Streamlit app.
//
// This is a hand-rolled Streamlit component instead of one built on
// streamlit-component-lib/React: the Streamlit <-> iframe protocol is just
// postMessage with a handful of message types, small enough to implement
// directly and avoid pulling in an npm/React build pipeline for something
// this size. See https://docs.streamlit.io/develop/concepts/custom-components
// for the (React-oriented) reference implementation this mirrors.
import { EditorState } from "@codemirror/state";
import { EditorView, keymap, lineNumbers, highlightActiveLine } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { syntaxHighlighting, HighlightStyle, StreamLanguage } from "@codemirror/language";
import { markdown } from "@codemirror/lang-markdown";
import { html } from "@codemirror/lang-html";
import { stex } from "@codemirror/legacy-modes/mode/stex";
import { tags as t } from "@lezer/highlight";

const DEBOUNCE_MS = 500;

// Dracula (https://draculatheme.com/) -- fixed rather than following
// Streamlit's light/dark setting: this editor lives in its own iframe, a
// separate document that doesn't inherit the outer page's theme at all, so
// "adapt to Streamlit's theme" would need its own plumbing. A fixed dark
// theme is simpler and also just directly fixes the actual complaint
// (default/unstyled text being unreadable against a dark background).
const dracula = {
  background: "#282a36",
  currentLine: "#44475a",
  foreground: "#f8f8f2",
  comment: "#6272a4",
  cyan: "#8be9fd",
  green: "#50fa7b",
  orange: "#ffb86c",
  pink: "#ff79c6",
  purple: "#bd93f9",
  red: "#ff5555",
  yellow: "#f1fa8c",
};

const draculaEditorTheme = EditorView.theme(
  {
    "&": { color: dracula.foreground, backgroundColor: dracula.background },
    ".cm-content": { caretColor: dracula.foreground },
    "&.cm-focused .cm-cursor": { borderLeftColor: dracula.foreground },
    "&.cm-selectionBackground, ::selection, .cm-content ::selection": {
      backgroundColor: `${dracula.currentLine} !important`,
    },
    ".cm-activeLine": { backgroundColor: dracula.currentLine },
    ".cm-activeLineGutter": { backgroundColor: dracula.currentLine },
    ".cm-gutters": {
      backgroundColor: dracula.background,
      color: dracula.comment,
      border: "none",
    },
  },
  { dark: true }
);

const draculaHighlightStyle = HighlightStyle.define([
  { tag: [t.comment, t.blockComment, t.lineComment], color: dracula.comment, fontStyle: "italic" },
  { tag: [t.keyword, t.controlKeyword, t.moduleKeyword], color: dracula.pink },
  { tag: [t.string, t.special(t.string)], color: dracula.yellow },
  { tag: [t.number, t.integer, t.float], color: dracula.purple },
  { tag: [t.bool, t.null], color: dracula.purple },
  { tag: [t.variableName, t.propertyName], color: dracula.foreground },
  { tag: [t.definition(t.variableName), t.definition(t.propertyName)], color: dracula.green },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: dracula.green },
  { tag: t.attributeName, color: dracula.green },
  { tag: t.attributeValue, color: dracula.yellow },
  { tag: t.tagName, color: dracula.pink },
  { tag: [t.angleBracket, t.punctuation, t.bracket, t.paren, t.brace], color: dracula.foreground },
  { tag: t.operator, color: dracula.pink },
  { tag: [t.className, t.typeName], color: dracula.cyan },
  { tag: t.meta, color: dracula.comment },
  { tag: t.link, color: dracula.cyan, textDecoration: "underline" },
  { tag: t.url, color: dracula.cyan },
  { tag: t.heading, color: dracula.purple, fontWeight: "bold" },
  { tag: t.strong, fontWeight: "bold", color: dracula.orange },
  { tag: t.emphasis, fontStyle: "italic", color: dracula.yellow },
  { tag: t.strikethrough, textDecoration: "line-through" },
  { tag: t.quote, color: dracula.yellow, fontStyle: "italic" },
  { tag: [t.list, t.processingInstruction], color: dracula.pink },
  { tag: t.monospace, color: dracula.green },
  { tag: t.invalid, color: dracula.red },
]);

// Fenced code block languages available inside the markdown, e.g.
// ```html or ```latex / ```tex blocks. Anything else falls back to no
// highlighting, same as CodeMirror's markdown mode does by default.
const codeLanguages = (info) => {
  const lang = info.trim().toLowerCase();
  if (lang === "html") return html().language;
  if (lang === "latex" || lang === "tex") return StreamLanguage.define(stex).language;
  return null;
};

let view = null;
let lastKey = null;
let lastFlushToken = null;
let debounceTimer = null;
let lastSentDoc = null;

function sendToStreamlit(message) {
  window.parent.postMessage({ isStreamlitMessage: true, ...message }, "*");
}

function setFrameHeight() {
  const height = document.documentElement.scrollHeight;
  sendToStreamlit({ type: "streamlit:setFrameHeight", height });
}

function sendValue(doc) {
  if (doc === lastSentDoc) return;
  lastSentDoc = doc;
  sendToStreamlit({ type: "streamlit:setComponentValue", value: doc });
}

function scheduleSendValue(doc) {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => sendValue(doc), DEBOUNCE_MS);
}

// Send immediately rather than waiting out the debounce, and cancel any
// pending debounced send (it would just be a redundant no-op once this
// runs, since sendValue() no-ops on an unchanged doc anyway).
function flushNow(doc) {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
  sendValue(doc);
}

// Unconditional version of flushNow, used only for a Python-requested
// flush (see the flush_token handling in onRender below): always sends,
// even if the doc looks unchanged from the last thing we sent. This is
// what Python's Render handler blocks on to know the save actually landed
// -- if this used the same dedup as flushNow/sendValue, an unchanged doc
// would never produce a new Streamlit widget value, and Python would have
// nothing to react to.
function forceSend(doc) {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
  lastSentDoc = doc;
  sendToStreamlit({ type: "streamlit:setComponentValue", value: doc });
}

function makeState(doc) {
  return EditorState.create({
    doc,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap]),
      draculaEditorTheme,
      syntaxHighlighting(draculaHighlightStyle, { fallback: true }),
      markdown({ codeLanguages }),
      // The one line that actually matters for the "browser spellcheck"
      // requirement: CodeMirror 6's editable surface is a real
      // contenteditable DOM tree (unlike e.g. Ace, which paints styled
      // divs/canvas over an offscreen textarea), so turning this on makes
      // the browser's native spellcheck underline misspelled words -- and
      // right-click -> "Add to dictionary" already works for free, since
      // that's the browser's own per-profile dictionary, not app state.
      EditorView.contentAttributes.of({
        spellcheck: "true",
        autocorrect: "off",
        autocapitalize: "off",
      }),
      EditorView.lineWrapping,
      EditorView.updateListener.of((update) => {
        if (update.docChanged) {
          scheduleSendValue(update.state.doc.toString());
        }
        if (update.heightChanged || update.docChanged) {
          setFrameHeight();
        }
      }),
      // Flush immediately on blur rather than leaving the last edit(s)
      // sitting in the debounce window. Clicking Render (or any other
      // Streamlit control) blurs this editor first, as part of the same
      // click -- so this is what guarantees the file on disk actually
      // reflects what's in the editor at the moment Render runs, instead
      // of racing the debounce timer.
      EditorView.domEventHandlers({
        blur: (_event, editorView) => flushNow(editorView.state.doc.toString()),
      }),
    ],
  });
}

function mount(initialDoc, height) {
  const container = document.getElementById("editor");
  container.style.height = `${height}px`;
  lastSentDoc = initialDoc;
  view = new EditorView({
    state: makeState(initialDoc),
    parent: container,
  });
}

function onRender(event) {
  const data = event.data;
  if (!data || data.type !== "streamlit:render") return;
  const args = data.args || {};
  const doc = typeof args.value === "string" ? args.value : "";
  const key = args.doc_id;
  const height = typeof args.height === "number" ? args.height : 700;
  const flushToken = args.flush_token;

  if (!view) {
    mount(doc, height);
    lastKey = key;
    lastFlushToken = flushToken;
    setFrameHeight();
    return;
  }

  // Only reload the document when the *file identity* changed. Every
  // Streamlit rerun re-sends a render event, including the one triggered by
  // our own setComponentValue() call echoing back through Python -- if we
  // reset the doc on every render, typing would get its cursor/selection
  // clobbered mid-edit on each debounce tick.
  if (key !== lastKey) {
    lastKey = key;
    lastFlushToken = flushToken;
    lastSentDoc = doc;
    view.setState(makeState(doc));
    setFrameHeight();
    return;
  }

  // Python bumps flush_token right when Render is clicked and blocks on
  // seeing a reply before it actually builds -- see the "Render" comment
  // in streamlit_app.py for why relying on the debounce/blur alone isn't
  // enough (postMessage delivery to the parent frame isn't guaranteed to
  // finish before the click's own Streamlit rerun request goes out).
  if (flushToken !== undefined && flushToken !== lastFlushToken) {
    lastFlushToken = flushToken;
    forceSend(view.state.doc.toString());
  }
}

window.addEventListener("message", onRender);
sendToStreamlit({ type: "streamlit:componentReady", apiVersion: 1 });
