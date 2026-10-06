// Browser side of the Cornell notes Flask app (see ../flask_app.py for the
// JSON API this talks to, and ../frontend_src/editor.js for
// window.CodeEditor). Everything persistent lives on disk server-side; this
// file only holds the open file's in-progress form state.
"use strict";

const CONFIG = JSON.parse(document.getElementById("config").textContent);
const TZ_SET = new Set(CONFIG.tzOptions);
const AUTOSAVE_MS = 500;
// Same order as header_form.FORM_FIELDS, so snapshots compare reliably.
const FORM_FIELDS = ["topic", "location", "date", "start", "end", "timezone", "tz_hint", "attendees"];

const $ = (selector) => document.querySelector(selector);

// Tiny DOM builder: h("button", { class: "x", onclick: fn }, "Label").
// on* function attributes become event listeners; true/false toggle
// boolean attributes; everything else is set as a string attribute.
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (value === true) el.setAttribute(key, "");
    else if (value !== false && value != null) el.setAttribute(key, value);
  }
  el.append(...children.flat().filter((c) => c != null));
  return el;
}

// localStorage only remembers per-browser conveniences (last file, pane
// height); it can be unavailable (private windows, blocked storage).
const prefs = {
  get(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      /* not essential */
    }
  },
};

const state = {
  files: [],
  selected: null,
  header: null, // the selected file's header form values (FORM_FIELDS)
  lastSaved: {}, // filename -> snapshot() of its last successful save
  rendered: {}, // filename -> snapshot() at its last successful render
  pdf: null, // { name, version } of the PDF in the preview pane
  busy: false, // a render is in flight
  buildOk: null,
  buildLog: "",
  confirmDelete: false,
  assets: { dir: "", folders: [], files: [], folder_paths: [""], all_files: [] },
  selectedAssets: new Set(),
};

// --- API ----------------------------------------------------------------

async function api(method, url, body, { keepalive = false } = {}) {
  const options = { method, headers: {}, keepalive };
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  let data = null;
  try {
    data = await response.json();
  } catch {
    /* non-JSON error page */
  }
  if (!response.ok) throw new Error((data && data.error) || `${response.status} ${response.statusText}`);
  return data;
}

const fileUrl = (name) => `api/files/${encodeURIComponent(name)}`;

// --- Messages -------------------------------------------------------------

function showMessage(text, kind = "error") {
  const el = h(
    "div",
    { class: `msg ${kind}` },
    h("span", {}, text),
    h("button", { type: "button", class: "link dismiss", "aria-label": "Dismiss", onclick: () => el.remove() }, "×")
  );
  $("#messages").append(el);
  return el;
}

// One persistent autosave warning rather than a new one per failed save --
// saves retry on every edit, so a lasting failure (permissions, disk full)
// would otherwise stack up a message per keystroke.
let autosaveWarning = null;
function setAutosaveWarning(text) {
  if (autosaveWarning) autosaveWarning.remove();
  autosaveWarning = text ? showMessage(text, "warning") : null;
}

// --- Header form + autosave ----------------------------------------------

const headerInputs = [...document.querySelectorAll("[data-field]")];

function snapshot(header, markdown) {
  return JSON.stringify([FORM_FIELDS.map((name) => header[name] || ""), markdown]);
}

function currentSnapshot() {
  return state.header ? snapshot(state.header, CodeEditor.getDoc()) : null;
}

function fillHeader(form) {
  for (const input of headerInputs) input.value = form[input.dataset.field] || "";
}

let saveTimer = null;
let saveChain = Promise.resolve(true);

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveNow, AUTOSAVE_MS);
  updateStatus();
}

// Writes the selected file's header + markdown to disk if either changed
// since the last save. Saves are chained so they land in order; resolves
// to whether the save (if any) succeeded.
function saveNow() {
  clearTimeout(saveTimer);
  saveTimer = null;
  const file = state.selected;
  if (!file || !state.header) return saveChain;
  const header = { ...state.header };
  const markdown = CodeEditor.getDoc();
  const snap = snapshot(header, markdown);
  saveChain = saveChain.then(async () => {
    if (state.lastSaved[file] === snap) return true;
    try {
      await api("PUT", fileUrl(file), { header, markdown });
      state.lastSaved[file] = snap;
      setAutosaveWarning(null);
      return true;
    } catch (err) {
      setAutosaveWarning(err.message);
      return false;
    }
  });
  return saveChain;
}

// Last-chance save as the tab closes or is hidden: a keepalive fetch
// started right away (not queued behind saveChain), so the browser still
// delivers it after the page is gone.
function saveOnLeave() {
  const file = state.selected;
  if (!file || !state.header) return;
  const header = { ...state.header };
  const markdown = CodeEditor.getDoc();
  const snap = snapshot(header, markdown);
  if (state.lastSaved[file] === snap) return;
  clearTimeout(saveTimer);
  state.lastSaved[file] = snap;
  api("PUT", fileUrl(file), { header, markdown }, { keepalive: true }).catch(() => {
    delete state.lastSaved[file];
  });
}

function wireHeaderInputs() {
  for (const input of headerInputs) {
    const field = input.dataset.field;
    if (field === "timezone") continue;
    input.addEventListener("input", () => {
      if (!state.header) return;
      state.header[field] = input.value;
      scheduleSave();
    });
  }
  // Timezone is a free-text input over a datalist (so it's searchable), so
  // only commit a value that's actually one of the offered zones -- anything
  // else snaps back to the last valid choice.
  const tz = $("#tz-input");
  tz.addEventListener("change", () => {
    if (!state.header) return;
    if (tz.value && !TZ_SET.has(tz.value)) {
      tz.value = state.header.timezone;
      return;
    }
    state.header.timezone = tz.value;
    scheduleSave();
  });
}

// --- Files ----------------------------------------------------------------

let loadToken = 0;

async function selectFile(name) {
  const token = ++loadToken;
  if (state.selected && state.header) await saveNow();
  state.selected = name;
  state.header = null;
  state.confirmDelete = false;
  prefs.set("selectedFile", name);
  updateFileControls();
  try {
    const data = await api("GET", fileUrl(name));
    if (token !== loadToken) return; // superseded by a later selection
    state.header = Object.fromEntries(FORM_FIELDS.map((f) => [f, data.header[f] || ""]));
    fillHeader(state.header);
    CodeEditor.setDoc(data.markdown);
    state.pdf = data.pdf;
    $("#editor-caption").textContent = name;
    updatePdf();
    updateStatus();
    // Writes back any defaults filled in on load (e.g. today's date for a
    // new file, or a legacy "time" field migrated to timezone/location).
    saveNow();
  } catch (err) {
    showMessage(err.message);
  }
}

function setFiles(files) {
  state.files = files;
  const select = $("#file-select");
  select.replaceChildren(...files.map((f) => h("option", { value: f }, f)));
  if (state.selected) select.value = state.selected;
  const none = files.length === 0;
  $("#no-files").hidden = !none;
  $("#header-box").hidden = none;
  $("#panes").hidden = none;
  if (none) {
    state.selected = null;
    state.header = null;
  }
  updateFileControls();
  applyPaneHeight(); // the editor can't measure its toolbar while hidden
}

function updateFileControls() {
  const { busy, selected, confirmDelete } = state;
  $("#file-select").value = selected || "";
  $("#new-file-btn").disabled = busy;
  $("#create-file-btn").disabled = busy;
  $("#render-btn").disabled = busy || !selected;
  $("#delete-file-btn").hidden = !selected || confirmDelete;
  $("#delete-file-btn").disabled = busy;
  $("#delete-confirm").hidden = !selected || !confirmDelete;
  $("#delete-name").textContent = selected || "";
  $("#confirm-delete-btn").disabled = busy;
  $("#download-btn").setAttribute("aria-disabled", String(busy || !state.pdf));
}

async function createFile() {
  const input = $("#new-file-name");
  const error = $("#new-file-error");
  error.hidden = true;
  try {
    const data = await api("POST", "api/files", { name: input.value });
    input.value = "";
    $("#new-file-pop").hidePopover();
    setFiles(data.files);
    await selectFile(data.file);
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
}

async function deleteFile() {
  const name = state.selected;
  // Let any pending save for this file finish (or be dropped) first, so it
  // can't land after the delete and fail with "not found".
  clearTimeout(saveTimer);
  await saveChain;
  try {
    const data = await api("DELETE", fileUrl(name));
    delete state.lastSaved[name];
    delete state.rendered[name];
    state.selected = null;
    state.header = null;
    state.confirmDelete = false;
    setFiles(data.files);
    if (data.files.length) await selectFile(data.files[0]);
  } catch (err) {
    state.confirmDelete = false;
    updateFileControls();
    showMessage(err.message);
  }
}

// --- Render + status ------------------------------------------------------

async function renderPdf() {
  const file = state.selected;
  if (!file || !state.header || state.busy) return;
  clearTimeout(saveTimer);
  const header = { ...state.header };
  const markdown = CodeEditor.getDoc();
  state.busy = true;
  updateFileControls();
  const button = $("#render-btn");
  button.textContent = "Rendering…";
  try {
    // An in-flight autosave landing after the render's own save would be
    // harmless (same or older content), but wait it out anyway so the two
    // never interleave on disk.
    await saveChain;
    const result = await api("POST", `${fileUrl(file)}/render`, { header, markdown, build_id: CONFIG.buildId });
    if (result.saved) state.lastSaved[file] = snapshot(header, markdown);
    state.buildOk = result.ok;
    state.buildLog = result.log;
    if (result.ok) state.rendered[file] = snapshot(header, markdown);
    if (result.pdf && state.selected === file) state.pdf = result.pdf;
  } catch (err) {
    state.buildOk = false;
    state.buildLog = err.message;
  } finally {
    state.busy = false;
    button.textContent = "Render";
    updateFileControls();
    updatePdf();
    updateStatus();
  }
}

function updateStatus() {
  const status = $("#build-status");
  status.hidden = state.buildOk === null;
  status.className = `pill ${state.buildOk ? "ok" : "fail"}`;
  status.textContent = state.buildOk ? "Build succeeded." : "Build failed.";

  $("#build-log-box").hidden = !(state.buildOk === false && state.buildLog);
  $("#build-log").textContent = state.buildLog;

  // The preview is stale whenever the header/markdown have changed since
  // this file's last successful render -- or it was never rendered this
  // session, and the PDF shown is just whatever was already on disk.
  const stale = Boolean(state.pdf && state.selected && state.rendered[state.selected] !== currentSnapshot());
  $("#stale-warning").hidden = !stale;
}

// --- Panes ------------------------------------------------------------------

function paneHeight() {
  const percent = parseInt($("#pane-height").value, 10) || 100;
  return Math.round((CONFIG.basePaneHeight * percent) / 100);
}

function applyPaneHeight() {
  const height = paneHeight();
  CodeEditor.setHeight(height);
  const frame = $("#pdf-host iframe");
  if (frame) frame.style.height = `${height}px`;
}

function updatePdf() {
  const host = $("#pdf-host");
  const download = $("#download-btn");
  if (!state.pdf) {
    $("#pdf-caption").textContent = "";
    host.replaceChildren(h("div", { class: "info" }, "No PDF yet -- click Render."));
    download.removeAttribute("href");
    updateFileControls();
    return;
  }
  const name = encodeURIComponent(state.pdf.name);
  $("#pdf-caption").textContent = state.pdf.name;
  // #view=FitH (honored by Chromium's built-in PDF viewer) scales the page
  // to the frame's *width* on load. Plain Fit letterboxes the page whenever
  // the frame is proportionally wider than it; FitH always fills the width,
  // at the cost of scrolling inside the frame when the pane is shorter than
  // a full page. ?v= busts the cache after each re-render.
  const src = `pdf/${name}?v=${state.pdf.version}#view=FitH`;
  let frame = host.querySelector("iframe");
  if (!frame) {
    frame = h("iframe", { title: "PDF preview" });
    host.replaceChildren(frame);
  }
  if (frame.getAttribute("src") !== src) frame.setAttribute("src", src);
  frame.style.height = `${paneHeight()}px`;
  download.href = `pdf/${name}?download=1`;
  updateFileControls();
}

// --- Assets -----------------------------------------------------------------

const assetDisplayDir = (dir) => (dir ? `assets/${dir}` : "assets");
const joinDir = (dir, name) => (dir ? `${dir}/${name}` : name);

async function loadAssets(dir = state.assets.dir) {
  try {
    applyAssets(await api("GET", `api/assets?dir=${encodeURIComponent(dir)}`));
  } catch (err) {
    showMessage(err.message);
  }
}

async function assetAction(method, url, body) {
  try {
    applyAssets(await api(method, url, body));
    return true;
  } catch (err) {
    showMessage(err.message);
    return false;
  }
}

function applyAssets(data) {
  if (data.dir !== state.assets.dir) state.selectedAssets.clear();
  state.assets = data;
  const names = new Set(data.files.map((f) => f.name));
  for (const name of state.selectedAssets) if (!names.has(name)) state.selectedAssets.delete(name);
  for (const error of data.errors || []) showMessage(error);
  CodeEditor.setAssets(data.all_files);
  $("#assets-summary").textContent = `Assets (${data.all_files.length})`;
  renderAssetsPanel();
}

let popoverCount = 0;

// A button that opens a popover built by `build(close)`.
function popoverButton(label, build) {
  const id = `pop-${++popoverCount}`;
  const pop = h("div", { popover: true, id, class: "pop" });
  pop.append(...build(() => pop.hidePopover()));
  return [h("button", { type: "button", popovertarget: id }, label), pop];
}

async function copyText(text, button) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // navigator.clipboard only exists in secure contexts (https or
    // localhost) -- not when the app is opened over plain http from
    // another machine on the network.
    const scratch = h("textarea", {}, text);
    document.body.append(scratch);
    scratch.select();
    document.execCommand("copy");
    scratch.remove();
  }
  button.textContent = "Copied";
  setTimeout(() => (button.textContent = "Copy"), 1200);
}

function renderBreadcrumbs(dir) {
  const parts = dir ? dir.split("/") : [];
  const crumbs = [h("button", { type: "button", class: "link", disabled: !dir, onclick: () => loadAssets("") }, "assets")];
  parts.forEach((part, i) => {
    const target = parts.slice(0, i + 1).join("/");
    crumbs.push(
      h("span", { class: "sep" }, "/"),
      h("button", { type: "button", class: "link", disabled: target === dir, onclick: () => loadAssets(target) }, part)
    );
  });
  return h("div", { class: "crumbs" }, crumbs);
}

function renderFolderRow(dir, name) {
  const target = joinDir(dir, name);
  const [renameBtn, renamePop] = popoverButton("Rename", (close) => {
    const input = h("input", { type: "text", value: name, "aria-label": "New name" });
    const confirm = async () => {
      if (await assetAction("PATCH", "api/assets/folders", { dir, name, new_name: input.value })) close();
    };
    input.addEventListener("keydown", (e) => e.key === "Enter" && confirm());
    return [h("label", {}, "New name", input), h("button", { type: "button", onclick: confirm }, "Confirm")];
  });
  const [deleteBtn, deletePop] = popoverButton("Delete", (close) => [
    h("p", {}, "Delete folder ", h("code", {}, name), " and everything inside it?"),
    h("button", {
      type: "button",
      class: "danger",
      onclick: async () => {
        close();
        await assetAction("DELETE", "api/assets/folders", { dir, name });
      },
    }, "Confirm"),
  ]);
  return h(
    "div",
    { class: "asset-row folder" },
    h("button", { type: "button", class: "folder-btn", onclick: () => loadAssets(target) }, `📁 ${name}`),
    renameBtn,
    renamePop,
    deleteBtn,
    deletePop
  );
}

function renderFileRow(dir, file) {
  const path = `${assetDisplayDir(dir)}/${file.name}`;
  const url = `asset-files/${[...(dir ? dir.split("/") : []), file.name].map(encodeURIComponent).join("/")}`;
  const checkbox = h("input", { type: "checkbox", "aria-label": `Select ${file.name}`, checked: state.selectedAssets.has(file.name) });
  checkbox.addEventListener("change", () => {
    if (checkbox.checked) state.selectedAssets.add(file.name);
    else state.selectedAssets.delete(file.name);
    renderAssetsPanel();
  });
  const pathInput = h("input", { type: "text", class: "path mono", readonly: true, value: path, "aria-label": "Asset path" });
  pathInput.addEventListener("focus", () => pathInput.select());
  const copyBtn = h("button", { type: "button", class: "link", onclick: () => copyText(path, copyBtn) }, "Copy");
  const [deleteBtn, deletePop] = popoverButton("Delete", (close) => [
    h("p", {}, "Delete ", h("code", {}, file.name), "?"),
    h("button", {
      type: "button",
      class: "danger",
      onclick: async () => {
        close();
        await assetAction("DELETE", "api/assets/files", { dir, name: file.name });
      },
    }, "Confirm"),
  ]);
  return h(
    "div",
    { class: "asset-row file" },
    checkbox,
    file.image ? h("img", { class: "thumb", src: url, alt: "", loading: "lazy" }) : h("span"),
    h("div", { class: "inline-form" }, pathInput, copyBtn),
    h("span", { class: "muted size" }, `${(file.size / 1024).toFixed(1)} KB`),
    deleteBtn,
    deletePop
  );
}

function renderMoveControls(dir) {
  const selected = [...state.selectedAssets];
  if (!selected.length) return null;
  const destinations = state.assets.folder_paths.filter((p) => p !== dir);
  if (!destinations.length) return h("p", { class: "muted" }, "Create another folder to move the selected files into.");
  const select = h("select", { "aria-label": "Move to" }, destinations.map((p) => h("option", { value: p }, assetDisplayDir(p))));
  return h(
    "div",
    { class: "inline-form" },
    select,
    h("button", {
      type: "button",
      onclick: () => assetAction("POST", "api/assets/move", { dir, names: selected, dest: select.value }),
    }, `Move ${selected.length} selected`)
  );
}

function renderAssetsPanel() {
  const { dir, folders, files } = state.assets;

  const folderInput = h("input", { type: "text", placeholder: "New folder name", "aria-label": "New folder name" });
  const createFolder = () => assetAction("POST", "api/assets/folders", { dir, name: folderInput.value });
  folderInput.addEventListener("keydown", (e) => e.key === "Enter" && createFolder());

  const fileInput = h("input", { type: "file", multiple: true, "aria-label": "Add files" });
  const uploadBtn = h("button", { type: "button", disabled: true }, "Upload");
  fileInput.addEventListener("change", () => (uploadBtn.disabled = !fileInput.files.length));
  uploadBtn.addEventListener("click", () => {
    const form = new FormData();
    form.append("dir", dir);
    for (const f of fileInput.files) form.append("files", f);
    assetAction("POST", "api/assets/upload", form);
  });

  const children = [
    renderBreadcrumbs(dir),
    h("div", { class: "inline-form" }, folderInput, h("button", { type: "button", onclick: createFolder }, "Create folder")),
    h("div", { class: "inline-form" }, fileInput, uploadBtn),
    !folders.length && !files.length ? h("p", { class: "muted" }, "No folders or files here yet.") : null,
    h(
      "div",
      { class: "asset-list" },
      folders.map((name) => renderFolderRow(dir, name)),
      files.map((file) => renderFileRow(dir, file))
    ),
    renderMoveControls(dir),
  ];
  $("#assets-panel").replaceChildren(...children.filter(Boolean));
}

// --- Startup ----------------------------------------------------------------

async function init() {
  $("#tz-list").replaceChildren(...CONFIG.tzOptions.map((z) => h("option", { value: z })));

  const paneSelect = $("#pane-height");
  paneSelect.replaceChildren(...CONFIG.paneHeightOptions.map((p) => h("option", { value: p }, p)));
  const savedPct = prefs.get("paneHeightPct");
  paneSelect.value = CONFIG.paneHeightOptions.includes(savedPct) ? savedPct : "100%";
  paneSelect.addEventListener("change", () => {
    prefs.set("paneHeightPct", paneSelect.value);
    applyPaneHeight();
  });

  CodeEditor.mount($("#editor-host"), {
    height: paneHeight(),
    onChange: () => {
      saveNow();
      updateStatus();
    },
  });

  wireHeaderInputs();
  $("#file-select").addEventListener("change", (e) => selectFile(e.target.value));
  $("#create-file-btn").addEventListener("click", createFile);
  $("#new-file-name").addEventListener("keydown", (e) => e.key === "Enter" && createFile());
  $("#delete-file-btn").addEventListener("click", () => {
    state.confirmDelete = true;
    updateFileControls();
  });
  $("#cancel-delete-btn").addEventListener("click", () => {
    state.confirmDelete = false;
    updateFileControls();
  });
  $("#confirm-delete-btn").addEventListener("click", deleteFile);
  $("#render-btn").addEventListener("click", renderPdf);
  window.addEventListener("pagehide", saveOnLeave);
  document.addEventListener("visibilitychange", () => document.visibilityState === "hidden" && saveOnLeave());

  updatePdf();
  loadAssets("");
  try {
    const { files } = await api("GET", "api/files");
    setFiles(files);
    const remembered = prefs.get("selectedFile");
    if (files.length) await selectFile(files.includes(remembered) ? remembered : files[0]);
  } catch (err) {
    showMessage(err.message);
  }
}

init();
