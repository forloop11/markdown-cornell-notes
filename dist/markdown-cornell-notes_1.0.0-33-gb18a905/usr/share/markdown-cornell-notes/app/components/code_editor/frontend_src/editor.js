// CodeMirror 6 editor for the Cornell notes Streamlit app.
//
// This is a hand-rolled Streamlit component instead of one built on
// streamlit-component-lib/React: the Streamlit <-> iframe protocol is just
// postMessage with a handful of message types, small enough to implement
// directly and avoid pulling in an npm/React build pipeline for something
// this size. See https://docs.streamlit.io/develop/concepts/custom-components
// for the (React-oriented) reference implementation this mirrors.
import { EditorState, EditorSelection } from "@codemirror/state";
import { EditorView, keymap, lineNumbers, highlightActiveLine } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { syntaxHighlighting, HighlightStyle, StreamLanguage } from "@codemirror/language";
import { markdown } from "@codemirror/lang-markdown";
import { html } from "@codemirror/lang-html";
import { stex } from "@codemirror/legacy-modes/mode/stex";
import { tags as t } from "@lezer/highlight";
import { autocompletion, startCompletion } from "@codemirror/autocomplete";

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
      backgroundColor: "rgba(189, 147, 249, 0.35) !important",
    },
    ".cm-activeLine": { backgroundColor: dracula.currentLine },
    ".cm-activeLineGutter": { backgroundColor: dracula.currentLine },
    ".cm-gutters": {
      backgroundColor: dracula.background,
      color: dracula.comment,
      border: "none",
    },
    // @codemirror/autocomplete's own baseTheme otherwise renders the
    // completion tooltip in its stock light colors, clashing with
    // everything else in this always-dark editor.
    ".cm-tooltip.cm-tooltip-autocomplete": {
      backgroundColor: dracula.currentLine,
      border: `1px solid ${dracula.comment}`,
    },
    ".cm-tooltip-autocomplete ul li[aria-selected]": { backgroundColor: dracula.purple },
    // .cm-completionLabel/-Detail set their own color, which (being a rule
    // on the element itself rather than inherited) would otherwise win
    // over the selected-row background-only rule above and leave text
    // light-on-light against the purple highlight -- so the selected
    // state needs its own, more specific override for both.
    ".cm-completionLabel": { color: dracula.foreground },
    ".cm-completionDetail": { color: dracula.comment, fontStyle: "italic" },
    ".cm-completionMatchedText": { color: dracula.pink, textDecoration: "none" },
    ".cm-tooltip-autocomplete ul li[aria-selected] .cm-completionLabel": { color: dracula.background },
    ".cm-tooltip-autocomplete ul li[aria-selected] .cm-completionDetail": { color: dracula.background },
    ".cm-tooltip-autocomplete ul li[aria-selected] .cm-completionMatchedText": {
      color: dracula.background,
      fontWeight: "bold",
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
// Filenames from assets/ (see pipeline.list_asset_files() in the Python
// side), used by assetPathCompletions below. Updated on every render event
// rather than only when the doc/key changes, since the asset list can
// change (upload/delete) without the selected file changing.
let assetFiles = [];

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

// Tab isn't bound by @codemirror/commands' defaultKeymap (that's what
// @codemirror/commands' separate indentWithTab is for, which we don't use
// since we want a literal 2-space insert rather than indent-unit-aware
// indent/dedent). Without this binding, Tab falls through to the browser's
// native focus-navigation on the contenteditable surface, tabbing out of
// the editor instead of typing.
function insertTab(view) {
  view.dispatch(view.state.replaceSelection("  "), { scrollIntoView: true });
  return true;
}

function makeState(doc) {
  return EditorState.create({
    doc,
    extensions: [
      lineNumbers(),
      highlightActiveLine(),
      history(),
      keymap.of([{ key: "Tab", run: insertTab }, ...defaultKeymap, ...historyKeymap]),
      draculaEditorTheme,
      syntaxHighlighting(draculaHighlightStyle, { fallback: true }),
      markdown({ codeLanguages }),
      autocompletion({ override: [slashSnippetCompletions, fenceLangCompletions, assetPathCompletions] }),
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

// Wraps each selected range in `before`/`after` (e.g. "**"/"**" for bold).
// An empty range gets `placeholder` inserted and selected instead, so
// typing immediately overwrites it; a non-empty range keeps its text
// selected after being wrapped, so re-clicking the same button toggles
// nothing but wrapping twice is harmless (mirrors GitHub's comment-box
// toolbar rather than true toggle behavior, which would need parsing the
// existing delimiters back out).
function wrapSelection(before, after = before, placeholder = "") {
  if (!view) return;
  view.dispatch(
    view.state.changeByRange((range) => {
      const text = view.state.sliceDoc(range.from, range.to) || placeholder;
      const from = range.from + before.length;
      return {
        changes: { from: range.from, to: range.to, insert: `${before}${text}${after}` },
        range: EditorSelection.range(from, from + text.length),
      };
    })
  );
  view.focus();
}

// Selects the URL placeholder rather than the link text, since the URL is
// what the user almost always needs to replace immediately after clicking.
function insertLink() {
  if (!view) return;
  const url = "https://";
  view.dispatch(
    view.state.changeByRange((range) => {
      const text = view.state.sliceDoc(range.from, range.to) || "link text";
      const urlStart = range.from + 1 + text.length + 2; // "[" + text + "]("
      return {
        changes: { from: range.from, to: range.to, insert: `[${text}](${url})` },
        range: EditorSelection.range(urlStart, urlStart + url.length),
      };
    })
  );
  view.focus();
}

// Leaves the cursor inside the empty parens (rather than selecting a
// placeholder, like insertLink does for its URL) so assetPathCompletions
// can immediately offer files from assets/ -- see startCompletion call at
// the end, which opens that dropdown right away instead of waiting for a
// keystroke.
function insertImage() {
  if (!view) return;
  view.dispatch(
    view.state.changeByRange((range) => {
      const alt = view.state.sliceDoc(range.from, range.to) || "alt text";
      const insert = `![${alt}]()`;
      const pathPos = range.from + insert.length - 1;
      return {
        changes: { from: range.from, to: range.to, insert },
        range: EditorSelection.cursor(pathPos),
      };
    })
  );
  view.focus();
  startCompletion(view);
}

function insertText(text) {
  if (!view) return;
  view.dispatch(
    view.state.changeByRange((range) => {
      const to = range.from + text.length;
      return { changes: { from: range.from, to: range.to, insert: text }, range: EditorSelection.cursor(to) };
    })
  );
  view.focus();
}

// Applies (or, if every touched line already has it, removes) a per-line
// prefix across all lines spanned by the selection -- used for blockquotes
// and list markers. `makePrefix(line, index)` returns the prefix to insert
// for that line (index is the line's position within the touched range, so
// numbered lists can count 1., 2., 3. ...); `matchPrefix` returns the
// length of an existing prefix to strip, or 0 if the line doesn't have one.
//
// Deliberately not routed through changeByRange like wrapSelection: with
// several changes spread across many lines, changeByRange would require
// hand-computing each change's offset in the *post-change* document to
// report back as the new range. state.update() instead remaps the
// existing selection through the changes automatically, which is exactly
// what's wanted here and needs no manual offset math.
function toggleLinePrefix(makePrefix, matchPrefix) {
  if (!view) return;
  const { state } = view;
  const range = state.selection.main;
  const startLine = state.doc.lineAt(range.from).number;
  const endLine = state.doc.lineAt(range.to).number;
  const lines = [];
  for (let ln = startLine; ln <= endLine; ln++) lines.push(state.doc.line(ln));
  const allPrefixed = lines.every((line) => matchPrefix(line.text) > 0);
  const changes = lines.map((line, i) =>
    allPrefixed
      ? { from: line.from, to: line.from + matchPrefix(line.text), insert: "" }
      : { from: line.from, insert: makePrefix(line, i) }
  );
  view.dispatch(state.update({ changes, scrollIntoView: true }));
  view.focus();
}

// Heading has no natural "selected span" the way list markers do, so it
// only ever acts on the cursor's own line: repeated clicks step
// # -> ## -> ### -> (none) -> # ... rather than toggling one fixed level.
function cycleHeading() {
  if (!view) return;
  const { state } = view;
  const line = state.doc.lineAt(state.selection.main.from);
  const match = line.text.match(/^(#{1,6})\s/);
  const level = match ? match[1].length : 0;
  const nextLevel = level >= 3 ? 0 : level + 1;
  const prefix = nextLevel === 0 ? "" : `${"#".repeat(nextLevel)} `;
  view.dispatch({
    changes: { from: line.from, to: line.from + (match ? match[0].length : 0), insert: prefix },
    scrollIntoView: true,
  });
  view.focus();
}

// Inserts `text` as its own new line right after the cursor's current line
// (or, if that line is already empty, in place of it) -- for entries that
// are whole-line/block constructs and can't just splice into a paragraph
// midstream: cue/summary directives, a table skeleton, a display-math
// line. Selects text.slice(selStart, selStart + selLength) in the result,
// so a placeholder inside it can be typed over immediately.
function insertOwnLineBlock(text, selStart, selLength) {
  if (!view) return;
  const { state } = view;
  const line = state.doc.lineAt(state.selection.main.to);
  const needsLeadingNewline = line.text.length > 0;
  const insertAt = needsLeadingNewline ? line.to : line.from;
  const offset = insertAt + (needsLeadingNewline ? 1 : 0);
  view.dispatch({
    changes: { from: insertAt, insert: needsLeadingNewline ? `\n${text}` : text },
    selection: EditorSelection.range(offset + selStart, offset + selStart + selLength),
    scrollIntoView: true,
  });
  view.focus();
}

// "^<page> " (cue) or "^^<page> " (summary) -- see markdown_to_pages.py's
// CUE_RE/SUMMARY_RE, which only match when one of these is the *whole*
// line. The page number always starts as a placeholder "1" (selected, so
// typing the real page number immediately overwrites it) rather than
// anything inferred from the cursor position: the source markdown has no
// idea which rendered PDF page it'll land on -- that's decided later by
// \cornellFlow's automatic \vsplit pagination -- so any guess here would
// be no better than the fixed default the docstring already says is safe
// (out-of-range page numbers clamp to the nearest real page instead of
// vanishing).
function insertPageNote(marker) {
  const prefix = `${marker}1 `;
  insertOwnLineBlock(prefix, marker.length, 1);
}

// "<!-- pagebreak -->" -- markdown_to_pages.py's PAGEBREAK_RE only matches
// when this is the *whole* line, same requirement as the cue/summary
// directives above. No variable part to select afterward, so the cursor
// just lands at the end of the inserted line, ready for Enter + more text.
function insertPagebreak() {
  const text = "<!-- pagebreak -->";
  insertOwnLineBlock(text, text.length, 0);
}

// A minimal 2-column pipe-table skeleton, header placeholder selected so
// typing immediately overwrites it.
function insertTable() {
  const header = "Header 1";
  insertOwnLineBlock(`| ${header} | Header 2 |\n| --- | --- |\n| Cell | Cell |\n`, 2, header.length);
}

// Display math ($$...$$) needs its own line the same way a table or cue
// entry does; inline math ($...$) is just a wrap, handled by wrapSelection
// via the TOOLBAR_GROUPS entry below instead.
function insertDisplayMath() {
  const placeholder = "x^2";
  insertOwnLineBlock(`$$${placeholder}$$`, 2, placeholder.length);
}

// --- Autocompletion -------------------------------------------------
//
// Three independent completion sources, wired up as autocompletion()'s
// `override` in makeState below. `override` replaces the language's own
// completion sources rather than adding to them -- markdown()'s built-in
// HTML-tag completion is the only thing that costs, and this app doesn't
// otherwise use inline HTML, so that's an acceptable trade for not having
// to reach into @codemirror/language's per-language completion data API.

// Only "html" and "latex"/"tex" actually get real syntax highlighting in
// this editor (see codeLanguages above) -- the other tags here are purely
// documentation of the block's content for readers of the raw markdown.
// They render as plain text in both this editor and the built PDF, since
// markdown_to_pages.py invokes pandoc with --no-highlight (see that
// file's markdown_to_latex): the tag never reaches a syntax highlighter
// either way. notes-example.md's own "```python" block is exactly this
// case -- a tag kept for readability, not rendering.
const FENCE_LANGUAGES = ["html", "latex", "tex", "python", "javascript", "bash", "json", "yaml", "text"];

// Matches right after a fenced-code opening ``` at the start of a line,
// with zero or more word characters already typed (e.g. "```py|").
function fenceLangCompletions(context) {
  const line = context.state.doc.lineAt(context.pos);
  const before = line.text.slice(0, context.pos - line.from);
  const match = /^```(\w*)$/.exec(before);
  if (!match) return null;
  return {
    from: line.from + 3,
    options: FENCE_LANGUAGES.map((label) => ({ label, type: "keyword" })),
    validFor: /^\w*$/,
  };
}

// Matches inside the target parens of a link or image -- "](assets/tux|" --
// and offers files from assets/ (see assetFiles, populated from Python's
// pipeline.list_asset_files() in onRender). Deliberately not anchored to
// "![" specifically: a plain [text](...) link pointing at an asset (e.g.
// linking out to a PDF handout) is just as valid as an image embed.
function assetPathCompletions(context) {
  const line = context.state.doc.lineAt(context.pos);
  const before = line.text.slice(0, context.pos - line.from);
  const match = /\]\(([^)\s]*)$/.exec(before);
  if (!match) return null;
  return {
    from: context.pos - match[1].length,
    options: assetFiles.map((name) => ({ label: `assets/${name}`, type: "text" })),
    validFor: /^[\w./-]*$/,
  };
}

// Wraps one of the existing toolbar action functions (wrapSelection,
// toggleLinePrefix, insertPageNote, etc.) so it can also be triggered by
// accepting a "/word" completion: first deletes the "/word" text the
// completion is replacing, then runs the action against the resulting
// (now-clean) selection -- exactly the state the action would see if the
// matching toolbar button had been clicked instead.
function applySnippet(action) {
  return (editorView, _completion, from, to) => {
    editorView.dispatch({ changes: { from, to, insert: "" } });
    action();
  };
}

const SNIPPETS = [
  { word: "bold", detail: "**bold text**", action: () => wrapSelection("**", "**", "bold text") },
  { word: "italic", detail: "*italic text*", action: () => wrapSelection("*", "*", "italic text") },
  { word: "strikethrough", detail: "~~text~~", action: () => wrapSelection("~~", "~~", "strikethrough text") },
  { word: "code", detail: "inline `code`", action: () => wrapSelection("`", "`", "code") },
  { word: "codeblock", detail: "fenced code block", action: () => wrapSelection("```\n", "\n```", "code") },
  { word: "quote", detail: "blockquote", action: () => toggleLinePrefix(() => "> ", (t) => (t.startsWith("> ") ? 2 : 0)) },
  { word: "link", detail: "[text](url)", action: insertLink },
  { word: "image", detail: "![alt](assets/...)", action: insertImage },
  { word: "table", detail: "pipe-table skeleton", action: insertTable },
  {
    word: "task",
    detail: "task list item",
    action: () =>
      toggleLinePrefix(
        () => "- [ ] ",
        (t) => (/^-\s\[[ xX]\]\s/.test(t) ? t.match(/^-\s\[[ xX]\]\s/)[0].length : 0)
      ),
  },
  { word: "hr", detail: "horizontal rule", action: () => insertText("\n---\n") },
  { word: "math", detail: "inline $math$", action: () => wrapSelection("$", "$", "x^2") },
  { word: "displaymath", detail: "display $$math$$", action: insertDisplayMath },
  { word: "cue", detail: "^<page> cue-column note", action: () => insertPageNote("^") },
  { word: "summary", detail: "^^<page> summary-band note", action: () => insertPageNote("^^") },
  { word: "pagebreak", detail: "force a page break", action: insertPagebreak },
];

// Matches a "/" that starts a word, only when it's at the start of a line
// or after whitespace -- NOT anywhere a "/" appears, since markdown is
// full of them in URLs and paths (e.g. "https://example.com/path"), where
// popping up a snippet dropdown after every slash would just be noise.
function slashSnippetCompletions(context) {
  const line = context.state.doc.lineAt(context.pos);
  const before = line.text.slice(0, context.pos - line.from);
  const match = /(?:^|\s)\/(\w*)$/.exec(before);
  if (!match) return null;
  const from = line.from + before.length - 1 - match[1].length;
  return {
    from,
    options: SNIPPETS.map(({ word, detail, action }) => ({
      label: `/${word}`,
      detail,
      apply: applySnippet(action),
    })),
    validFor: /^\/\w*$/,
  };
}

const TOOLBAR_GROUPS = [
  [
    { label: "B", title: "Bold", style: "font-weight:700", action: () => wrapSelection("**", "**", "bold text") },
    { label: "I", title: "Italic", style: "font-style:italic", action: () => wrapSelection("*", "*", "italic text") },
    {
      label: "S",
      title: "Strikethrough",
      style: "text-decoration:line-through",
      action: () => wrapSelection("~~", "~~", "strikethrough text"),
    },
    { label: "$", title: "Inline math ($...$)", action: () => wrapSelection("$", "$", "x^2") },
    { label: "x²", title: "Superscript (x^2^)", action: () => wrapSelection("^", "^", "2") },
    { label: "x₂", title: "Subscript (x~2~)", action: () => wrapSelection("~", "~", "2") },
  ],
  [
    { label: "H", title: "Heading (click to cycle levels)", action: cycleHeading },
    {
      label: ">",
      title: "Quote",
      action: () => toggleLinePrefix(() => "> ", (text) => (text.startsWith("> ") ? 2 : 0)),
    },
  ],
  [
    { label: "`", title: "Inline code", action: () => wrapSelection("`", "`", "code") },
    { label: "{ }", title: "Code block", action: () => wrapSelection("```\n", "\n```", "code") },
    { label: "Link", title: "Link", action: insertLink },
    { label: "Table", title: "Table", action: insertTable },
  ],
  [
    {
      label: "•",
      title: "Bullet list",
      action: () =>
        toggleLinePrefix(
          () => "- ",
          (text) => (/^[-*]\s/.test(text) ? text.match(/^[-*]\s/)[0].length : 0)
        ),
    },
    {
      label: "1.",
      title: "Numbered list",
      action: () =>
        toggleLinePrefix(
          (_line, i) => `${i + 1}. `,
          (text) => (/^\d+\.\s/.test(text) ? text.match(/^\d+\.\s/)[0].length : 0)
        ),
    },
    {
      label: "[x]",
      title: "Task list",
      action: () =>
        toggleLinePrefix(
          () => "- [ ] ",
          (text) => (/^-\s\[[ xX]\]\s/.test(text) ? text.match(/^-\s\[[ xX]\]\s/)[0].length : 0)
        ),
    },
  ],
  [
    { label: "HR", title: "Horizontal rule", action: () => insertText("\n---\n") },
    { label: "$$", title: "Display math ($$...$$)", action: insertDisplayMath },
  ],
  [
    { label: "^", title: "Add cue-column note (^<page> text)", action: () => insertPageNote("^") },
    { label: "^^", title: "Add summary-band note (^^<page> text)", action: () => insertPageNote("^^") },
    { label: "PB", title: "Page break (<!-- pagebreak -->)", action: insertPagebreak },
  ],
];

function buildToolbar() {
  const toolbar = document.createElement("div");
  toolbar.id = "toolbar";
  TOOLBAR_GROUPS.forEach((group, i) => {
    if (i > 0) {
      const divider = document.createElement("div");
      divider.className = "divider";
      toolbar.appendChild(divider);
    }
    group.forEach(({ label, title, style, action }) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.title = title;
      if (style) button.style.cssText = style;
      // Prevent the mousedown from blurring the editor (which would drop
      // its selection) before the click handler gets a chance to act on it.
      button.addEventListener("mousedown", (event) => event.preventDefault());
      button.addEventListener("click", action);
      toolbar.appendChild(button);
    });
  });
  return toolbar;
}

function mount(initialDoc, height) {
  const container = document.getElementById("editor");
  const toolbar = buildToolbar();
  container.parentElement.insertBefore(toolbar, container);
  // Subtract the toolbar's own rendered height from the editor's so the
  // two together still add up to the `height` Python passed in -- that
  // value is also used for the PDF pane's iframe height (see PANE_HEIGHT
  // in streamlit_app.py), and the two panes are expected to end up the
  // same total height so their bottoms line up.
  container.style.height = `${height - toolbar.offsetHeight}px`;
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
  assetFiles = Array.isArray(args.assets) ? args.assets : [];

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
