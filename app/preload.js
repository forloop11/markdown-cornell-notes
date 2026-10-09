// Bridge between the sandboxed renderer and main.js: exposes
// window.mcn.<name>(...args) for each of lib/api.js's CHANNELS, plus the
// main-process-only helpers below. Each call resolves to the result, or
// rejects with an Error carrying the user-facing message.
//
// Sandboxed preloads can't require() local files, so the channel list
// comes from main.js rather than being imported from lib/api.js.
"use strict";

const { contextBridge, ipcRenderer } = require("electron");

function unwrap(result) {
  if (result && "error" in result) throw new Error(result.error);
  return result.value;
}

const mcn = {};
for (const name of ipcRenderer.sendSync("mcn:channels")) {
  mcn[name] = async (...args) => unwrap(await ipcRenderer.invoke(`mcn:${name}`, ...args));
}

// Synchronous save, for when the page is reloading (see saveOnLeave in
// renderer/app.js).
mcn.saveFileSync = (filename, body) => unwrap(ipcRenderer.sendSync("mcn:saveFileSync", filename, body));

// Register `callback` (may be async) to run when the window is about to
// close; the window closes once it settles (see main.js's close handshake).
mcn.onBeforeClose = (callback) => {
  ipcRenderer.on("mcn:beforeClose", async () => {
    try {
      await callback();
    } finally {
      ipcRenderer.send("mcn:readyToClose");
    }
  });
};

// File > Open Project Folder... (also on the "no project" screen): resolves
// to whether a folder was picked; if so, the page reloads onto it.
mcn.chooseProject = async () => unwrap(await ipcRenderer.invoke("mcn:chooseProject"));

// "Download PDF": resolves to whether the user saved a copy.
mcn.savePdfAs = async (name) => unwrap(await ipcRenderer.invoke("mcn:savePdfAs", name));

contextBridge.exposeInMainWorld("mcn", mcn);
