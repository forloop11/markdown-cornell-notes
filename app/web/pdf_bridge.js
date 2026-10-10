// Connects window.PdfViewer (pdfviewer.js) to the Python side: `bridge` is
// ../webviews.py's PdfBridge, reached over a QWebChannel.
//
// Python -> page calls arrive as scripts run in this page
// (PdfViewer.load(...), PdfViewer.reveal(...)); page -> Python goes through
// bridge's slots.
"use strict";

new QWebChannel(qt.webChannelTransport, (channel) => {
  const bridge = channel.objects.bridge;
  PdfViewer.mount(document.getElementById("viewerContainer"), {
    onState: (state) => bridge.stateChanged(state.pages, state.page, state.percent, state.scale),
    onTextActivated: (text, fraction) => bridge.textActivated(text, fraction),
    onFind: (current, total) => bridge.findChanged(current, total),
  });
  bridge.ready();
});
