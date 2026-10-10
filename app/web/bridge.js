// Connects window.CodeEditor (editor.js) to the Python side: `bridge` is
// ../webviews.py's EditorBridge, reached over a QWebChannel.
//
// Python -> page calls arrive as scripts run in this page (MCN.setDoc(...),
// CodeEditor.setAssets(...)); page -> Python goes through bridge's slots.
"use strict";

new QWebChannel(qt.webChannelTransport, (channel) => {
  const bridge = channel.objects.bridge;
  // Which setDoc() the current document came from. Sent along with every
  // edit so Python can drop one that was still on its way when it replaced
  // the document (e.g. switched files) -- that text belongs to the old file.
  let generation = 0;

  CodeEditor.mount(document.getElementById("editor-host"), {
    height: window.innerHeight,
    onChange: (doc) => bridge.docChanged(generation, doc),
    onBlur: () => bridge.blurred(),
    onCursor: (line, lines) => bridge.cursorMoved(generation, line, lines),
  });
  window.addEventListener("resize", () => CodeEditor.setHeight(window.innerHeight));

  window.MCN = {
    setDoc(newGeneration, doc) {
      generation = newGeneration;
      CodeEditor.setDoc(doc);
    },
    // [generation, text]: what's in the editor right now.
    getDoc: () => [generation, CodeEditor.getDoc()],
  };
  bridge.ready();
});
