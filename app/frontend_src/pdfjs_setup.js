// Loads PDF.js for pdfviewer.js, in the order its pieces need:
//
// - pdfjs-dist's viewer components (pdf_viewer.mjs) read the library from
//   globalThis.pdfjsLib as they load, so it has to be there first --
//   importing this module ahead of them arranges that.
// - With globalThis.pdfjsWorker set, PDF.js parses documents on the main
//   thread instead of starting a web worker, which a page loaded from a
//   file: URL isn't allowed to do. The notes' PDFs are a few pages, so
//   that's quick enough.
//
// The "legacy" builds run on the older Chromium in Qt 6.8.
import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf.mjs";
import * as pdfjsWorker from "pdfjs-dist/legacy/build/pdf.worker.mjs";

globalThis.pdfjsLib = pdfjsLib;
globalThis.pdfjsWorker = pdfjsWorker;

export { pdfjsLib };
