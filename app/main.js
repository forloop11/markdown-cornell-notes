// Electron main process for the Cornell notes editor: one window over the
// project in the directory the app was launched from (see `make app` in
// ../Makefile), with lib/api.js's operations exposed to the renderer as
// IPC channels (see preload.js).
//
// The renderer is fully sandboxed (no Node, context isolation on) and only
// ever shows this app's own files: navigation away is blocked, and
// http(s)/mailto links (e.g. clicked inside the PDF preview) open in the
// system browser instead.
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require("electron");

const { Api, CHANNELS, PipelineError } = require("./lib/api");

// Same "operate on CWD" model as the CLI: `make app` (or the installed
// `markdown-cornell-notes app`) runs from the project directory.
const api = new Api({ projectRoot: process.cwd() });

const RENDERER_DIR = path.join(__dirname, "renderer");

let win = null;

// How long a closing window waits for the renderer to finish its last save
// (see the "close" handler in createWindow) before closing anyway.
const CLOSE_SAVE_TIMEOUT_MS = 3000;

// {value} on success, {error} for a user-facing failure -- preload.js turns
// the latter back into a thrown Error. (A plain throw across ipcMain.handle
// reaches the renderer wrapped in "Error invoking remote method ...".)
async function respond(fn) {
  try {
    return { value: await fn() };
  } catch (err) {
    if (err instanceof PipelineError) return { error: err.message };
    console.error(err);
    return { error: `Unexpected error: ${err.message}` };
  }
}

// Only this app's own page (not, say, a frame inside the PDF preview) may
// call into the main process.
function fromAppPage(event) {
  return win && event.senderFrame === win.webContents.mainFrame;
}

function registerIpc() {
  ipcMain.on("mcn:channels", (event) => {
    event.returnValue = fromAppPage(event) ? CHANNELS : [];
  });

  for (const name of CHANNELS) {
    ipcMain.handle(`mcn:${name}`, (event, ...args) =>
      fromAppPage(event) ? respond(() => api[name](...args)) : { error: "Refused." }
    );
  }

  // Last-chance save as the page reloads (see saveOnLeave in
  // renderer/app.js): synchronous, so the write is done before the page is
  // torn down. Closing the window goes through the close handshake in
  // createWindow instead, since Electron doesn't reliably run a closing
  // page's pagehide handlers.
  ipcMain.on("mcn:saveFileSync", (event, filename, body) => {
    if (!fromAppPage(event)) {
      event.returnValue = { error: "Refused." };
      return;
    }
    try {
      api.checkMarkdownFile(filename);
      api.save(filename, body);
      event.returnValue = { value: true };
    } catch (err) {
      event.returnValue = { error: err.message };
    }
  });

  // "Download PDF": a native save dialog, then a copy out of pdf/.
  // Resolves to whether the user went through with it.
  ipcMain.handle("mcn:savePdfAs", (event, name) => {
    if (!fromAppPage(event)) return { error: "Refused." };
    return respond(async () => {
      const source = api.pdfPath(name);
      const { canceled, filePath } = await dialog.showSaveDialog(win, {
        defaultPath: path.join(app.getPath("downloads"), name),
        filters: [{ name: "PDF", extensions: ["pdf"] }],
      });
      if (canceled || !filePath) return false;
      fs.copyFileSync(source, filePath);
      return true;
    });
  });
}

const isExternal = (url) => /^(https?|mailto):/i.test(url);

// Right-click menu: Electron has none by default. Spelling suggestions and
// "Add to dictionary" keep the editor's spellcheck as usable as it was in a
// browser.
function showContextMenu(params) {
  const { editFlags } = params;
  const items = [];
  if (params.misspelledWord) {
    for (const suggestion of params.dictionarySuggestions) {
      items.push({ label: suggestion, click: () => win.webContents.replaceMisspelling(suggestion) });
    }
    if (!params.dictionarySuggestions.length) items.push({ label: "No suggestions", enabled: false });
    items.push(
      {
        label: "Add to dictionary",
        click: () => win.webContents.session.addWordToSpellCheckerDictionary(params.misspelledWord),
      },
      { type: "separator" }
    );
  }
  if (params.isEditable) {
    items.push(
      { role: "undo", enabled: editFlags.canUndo },
      { role: "redo", enabled: editFlags.canRedo },
      { type: "separator" },
      { role: "cut", enabled: editFlags.canCut },
      { role: "copy", enabled: editFlags.canCopy },
      { role: "paste", enabled: editFlags.canPaste },
      { role: "selectAll", enabled: editFlags.canSelectAll }
    );
  } else if (params.selectionText) {
    items.push({ role: "copy" });
  }
  if (params.linkURL && isExternal(params.linkURL)) {
    items.push({ type: "separator" }, { label: "Open link in browser", click: () => shell.openExternal(params.linkURL) });
  }
  if (items.length) Menu.buildFromTemplate(items).popup({ window: win });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 900,
    minHeight: 600,
    title: "Markdown Cornell Notes",
    backgroundColor: "#0e1117",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      spellcheck: true,
    },
  });

  // The page's own <title> would otherwise replace this; showing the
  // project folder tells two app windows (two projects) apart.
  win.on("page-title-updated", (event) => event.preventDefault());
  win.setTitle(`Markdown Cornell Notes — ${api.pipeline.projectRoot}`);

  const { webContents } = win;
  webContents.setWindowOpenHandler(({ url }) => {
    if (isExternal(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  // The page never navigates itself (e.g. a file dropped on the window
  // would otherwise replace the app with that file).
  webContents.on("will-navigate", (event) => event.preventDefault());
  // A link clicked inside the PDF preview navigates its frame -- send web
  // links to the browser instead, and keep the frame on local files.
  webContents.on("will-frame-navigate", (event) => {
    if (event.isMainFrame) return;
    if (isExternal(event.url)) {
      event.preventDefault();
      shell.openExternal(event.url);
    } else if (!/^(file|chrome-extension|about|blob|data):/i.test(event.url)) {
      event.preventDefault();
    }
  });
  webContents.on("context-menu", (_event, params) => showContextMenu(params));

  // Closing waits for the renderer to save anything typed since the last
  // autosave: hold the close, ask the page to flush (preload.js's
  // onBeforeClose), and close for real once it reports back -- or after
  // CLOSE_SAVE_TIMEOUT_MS, so a hung page can't keep the window open.
  let closeRequested = false;
  win.on("close", (event) => {
    if (closeRequested) return;
    event.preventDefault();
    closeRequested = true;
    const finish = () => win && win.destroy();
    const timer = setTimeout(finish, CLOSE_SAVE_TIMEOUT_MS);
    ipcMain.once("mcn:readyToClose", () => {
      clearTimeout(timer);
      finish();
    });
    webContents.send("mcn:beforeClose");
  });

  win.on("closed", () => {
    win = null;
    api.cleanup();
  });

  win.loadFile(path.join(RENDERER_DIR, "index.html"));
}

app.whenReady().then(() => {
  registerIpc();
  createWindow();
});

// One window per project, and the project is fixed at launch -- so closing
// it ends the app, macOS included.
app.on("window-all-closed", () => app.quit());
