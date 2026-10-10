// The PDF preview pane, built on PDF.js (https://mozilla.github.io/pdf.js/).
//
// Bundled (see ../package.json's build:pdf script) into ../web/pdfviewer.js,
// which ../web/pdf.html loads in a Qt web view; ../web/pdf_bridge.js
// connects the window.PdfViewer API below to the Python side
// (../webviews.py's PdfView).
//
// Unlike a browser's built-in PDF viewer, this one the app can drive: it
// keeps its zoom and scroll position when the PDF is rebuilt, and can be
// scrolled to a piece of text (reveal) or asked what text was clicked --
// which is how the preview and the editor follow each other.
import { pdfjsLib } from "./pdfjs_setup.js";
import {
  EventBus,
  LinkTarget,
  PDFFindController,
  PDFLinkService,
  PDFViewer,
} from "pdfjs-dist/legacy/web/pdf_viewer.mjs";

// How a document opens: the whole page visible.
const DEFAULT_SCALE = "page-fit";
// Scale values that depend on the pane's size, and so need applying again
// when it changes.
const FITTED_SCALES = new Set(["page-fit", "page-width", "page-height", "auto"]);

let container = null;
let viewer = null;
let eventBus = null;
let linkService = null;
let doc = null;
// Counts load() calls, so a document that finishes loading after a newer
// one was asked for is dropped.
let generation = 0;
// What to restore once the document being loaded is laid out.
let restore = { key: null, scale: DEFAULT_SCALE, top: 0, left: 0 };
// Per page, the text PDF.js extracts (see pageTexts), until the document changes.
let texts = null;
let onState = () => {};
let onTextActivated = () => {};
let onFind = () => {};

// The same folding ../sync.py's normalize() applies to the markdown side,
// so text can be compared across the two: ligatures and other
// compatibility forms unfolded, typographic quotes and dashes made plain,
// case and runs of whitespace ignored.
function normalize(text) {
  return text
    .normalize("NFKC")
    .replace(/[‘’‚′]/g, "'")
    .replace(/[“”„″]/g, '"')
    .replace(/[‐-―−]/g, "-")
    .replace(/…/g, "...")
    .replace(/­/g, "")
    .replace(/-{2,}/g, "-")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function reportState() {
  if (!doc) {
    onState({ pages: 0, page: 0, percent: 0, scale: "" });
    return;
  }
  onState({
    pages: doc.numPages,
    page: viewer.currentPageNumber,
    percent: Math.round(viewer.currentScale * 100),
    scale: String(viewer.currentScaleValue),
  });
}

// Sets up the viewer in `el` (an absolutely positioned, scrolling element
// holding one empty child for the pages). `onState({pages, page, percent,
// scale})` is called when any of those change; `onTextActivated(text,
// fraction)` when text in the PDF is double-clicked, with how far through
// the document it is (0-1); `onFind(current, total)` as a search (see find)
// counts its matches and moves among them.
function mount(el, { onState: state, onTextActivated: activated, onFind: found } = {}) {
  container = el;
  onState = state || (() => {});
  onTextActivated = activated || (() => {});
  onFind = found || (() => {});
  eventBus = new EventBus();
  // Web links open outside the app (see ../webviews.py's LocalPage).
  linkService = new PDFLinkService({ eventBus, externalLinkTarget: LinkTarget.BLANK });
  const findController = new PDFFindController({ linkService, eventBus });
  viewer = new PDFViewer({ container, eventBus, linkService, findController });
  linkService.setViewer(viewer);
  const reportFind = ({ matchesCount }) => onFind(matchesCount?.current || 0, matchesCount?.total || 0);
  eventBus.on("updatefindmatchescount", reportFind);
  eventBus.on("updatefindcontrolstate", reportFind);

  eventBus.on("pagesinit", () => {
    viewer.currentScaleValue = restore.scale;
    container.scrollTop = restore.top;
    container.scrollLeft = restore.left;
    reportState();
  });
  eventBus.on("pagechanging", reportState);
  eventBus.on("scalechanging", reportState);

  // A fitted page follows the pane's size.
  // (On the next frame: resizing the pages inside the observer's own
  // callback would have it reporting on itself.)
  new ResizeObserver(() => {
    requestAnimationFrame(() => {
      if (doc && FITTED_SCALES.has(viewer.currentScaleValue)) {
        viewer.currentScaleValue = viewer.currentScaleValue;
      }
    });
  }).observe(container);

  container.addEventListener("dblclick", (event) => {
    const span = event.target.closest?.(".textLayer span");
    const page = event.target.closest?.(".page");
    if (!span || !page || !doc) return;
    // The clicked run of text, with what follows it on the line, since a
    // run can be a single word.
    let text = span.textContent;
    for (let next = span.nextElementSibling; next && text.length < 60; next = next.nextElementSibling) {
      if (next.tagName === "BR") break;
      text += next.textContent;
    }
    const number = Number(page.dataset.pageNumber);
    const within = (event.clientY - page.getBoundingClientRect().top) / page.clientHeight;
    onTextActivated(normalize(text), (number - 1 + Math.min(Math.max(within, 0), 1)) / doc.numPages);
  });
}

// Shows the PDF whose bytes are `base64`. `key` names the document (its
// file name): loading the same key again -- the PDF was rebuilt -- keeps
// the zoom and scroll position, a different one starts from the top.
async function load(base64, key) {
  const mine = ++generation;
  if (doc && key === restore.key) {
    restore = { key, scale: viewer.currentScaleValue, top: container.scrollTop, left: container.scrollLeft };
  } else {
    restore = { key, scale: DEFAULT_SCALE, top: 0, left: 0 };
  }
  const data = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  // isEvalSupported: the page's content security policy has no eval.
  const loaded = await pdfjsLib.getDocument({ data, isEvalSupported: false }).promise;
  if (mine !== generation) {
    loaded.destroy();
    return;
  }
  const previous = doc;
  doc = loaded;
  texts = null;
  lastQuery = "";
  viewer.setDocument(doc);
  linkService.setDocument(doc, null);
  if (previous) previous.destroy();
}

function clear() {
  generation++;
  if (doc) {
    viewer.setDocument(null);
    linkService.setDocument(null, null);
    doc.destroy();
    doc = null;
  }
  texts = null;
  restore = { key: null, scale: DEFAULT_SCALE, top: 0, left: 0 };
  reportState();
}

function zoomIn() {
  if (doc) viewer.increaseScale();
}

function zoomOut() {
  if (doc) viewer.decreaseScale();
}

// "page-fit", "page-width", or a number (1 = 100%).
function setScale(value) {
  if (doc) viewer.currentScaleValue = String(value);
}

function goToPage(number) {
  if (doc) viewer.currentPageNumber = Math.max(1, Math.min(number, doc.numPages));
}

// Each page's text as one normalized string, with where each of PDF.js's
// text runs starts in it -- so a match can be traced back to a place on
// the page.
async function pageTexts() {
  if (texts) return texts;
  const mine = generation;
  const collected = [];
  for (let number = 1; number <= doc.numPages; number++) {
    const page = await doc.getPage(number);
    const content = await page.getTextContent();
    let text = "";
    const starts = [];
    for (const item of content.items) {
      if (typeof item.str !== "string") continue;
      // Normalized run by run, so offsets into the whole stay offsets into runs.
      const piece = normalize(item.str);
      if (piece) {
        if (text && !text.endsWith(" ") && (item.str.startsWith(" ") || starts.at(-1)?.eol)) text += " ";
        starts.push({ offset: text.length, item, eol: item.hasEOL });
        text += piece;
        if (item.str.endsWith(" ")) text += " ";
      } else if (text && !text.endsWith(" ")) {
        text += " ";
      }
      if (item.hasEOL && starts.length) starts.at(-1).eol = true;
    }
    collected.push({ text, starts });
  }
  if (mine === generation) texts = collected;
  return collected;
}

// Scrolls to the first of `snippets` (normalized text, most specific
// first) found in the document, and flashes a marker over its line. Of
// several occurrences, the one nearest `fraction` (0-1) of the way through
// the document wins. Nothing happens if none is found, or if the match is
// already in view. Resolves to whether something was found.
async function reveal(snippets, fraction) {
  if (!doc) return false;
  const mine = generation;
  const pages = await pageTexts();
  if (mine !== generation) return false;
  for (const snippet of snippets) {
    const wanted = normalize(snippet);
    if (!wanted) continue;
    let best = null;
    pages.forEach(({ text, starts }, index) => {
      for (let at = text.indexOf(wanted); at !== -1; at = text.indexOf(wanted, at + 1)) {
        const where = (index + at / Math.max(text.length, 1)) / pages.length;
        const distance = Math.abs(where - fraction);
        if (!best || distance < best.distance) {
          const run = starts.filter((s) => s.offset <= at).at(-1) || starts[0];
          best = { distance, index, item: run.item };
        }
      }
    });
    if (best) {
      showMatch(best.index, best.item);
      return true;
    }
  }
  return false;
}

function showMatch(index, item) {
  const view = viewer.getPageView(index);
  if (!view?.div) return;
  const [, y] = view.viewport.convertToViewportPoint(item.transform[4], item.transform[5]);
  const height = Math.max((item.height || 10) * view.viewport.scale, 8);
  const top = view.div.offsetTop + view.div.clientTop + y - height;
  // Leave the view alone when the line is comfortably in it already.
  const margin = Math.min(60, container.clientHeight / 4);
  if (top < container.scrollTop + margin || top + height > container.scrollTop + container.clientHeight - margin) {
    container.scrollTop = Math.max(top - container.clientHeight / 3, 0);
  }
  const marker = document.createElement("div");
  marker.className = "sync-marker";
  marker.style.top = `${y - height - 2}px`;
  marker.style.height = `${height + 6}px`;
  view.div.append(marker);
  marker.addEventListener("animationend", () => marker.remove());
}

// Searches the PDF for `query`, highlighting every match and scrolling to
// one: the first, or -- called again with the same query -- the next
// (`backwards`: the previous). An empty query clears the search.
let lastQuery = "";
function find(query, backwards = false) {
  if (!doc) return;
  if (!query) {
    lastQuery = "";
    eventBus.dispatch("findbarclose", { source: window });
    onFind(0, 0);
    return;
  }
  eventBus.dispatch("find", {
    source: window,
    type: query === lastQuery ? "again" : "",
    query,
    caseSensitive: false,
    entireWord: false,
    highlightAll: true,
    findPrevious: backwards,
  });
  lastQuery = query;
}

window.PdfViewer = { mount, load, clear, zoomIn, zoomOut, setScale, goToPage, reveal, find };
