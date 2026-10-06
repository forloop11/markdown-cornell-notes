// Tests for lib/api.js -- the operations main.js exposes to the renderer
// over IPC -- run against an isolated project (see helpers.js). Rendering
// itself needs the full pandoc/TeX Live toolchain, so it's only covered up
// to the point where it would shell out to make.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const { Api, CHANNELS, PipelineError } = require("../lib/api");
const { REPO_ROOT, makeProject } = require("./helpers");

const HEADER = {
  topic: "Weekly Sync",
  location: "Zoom",
  date: "2026-08-23",
  start: "10:00",
  end: "10:30",
  timezone: "America/Detroit",
  tz_hint: "",
  attendees: "Lily",
};

function setup(t) {
  const root = makeProject(t);
  const api = new Api({ projectRoot: root, repoRoot: REPO_ROOT });
  api.pipeline.createMarkdownFile("notes");
  return { root, api };
}

test("config() carries the timezone list and pane options", (t) => {
  const { api } = setup(t);
  const config = api.config();
  assert.equal(config.initialized, true);
  assert.ok(config.tzOptions.includes("America/Detroit"));
  assert.ok(config.paneHeightOptions.includes("100%"));
  assert.equal(config.paneHeightOptions.at(-1), "200%");
});

test("an uninitialized directory reports initialized: false", (t) => {
  const root = makeProject(t);
  fs.rmSync(path.join(root, "md"), { recursive: true });
  const config = new Api({ projectRoot: root, repoRoot: REPO_ROOT }).config();
  assert.equal(config.initialized, false);
  assert.equal(config.projectRoot, root);
});

test("saveFile writes the composed yaml header and markdown; loadFile reads them back", async (t) => {
  const { root, api } = setup(t);
  assert.deepEqual(await api.saveFile("notes.md", { header: HEADER, markdown: "# Hi\n" }), { ok: true });
  assert.equal(api.pipeline.readHeader("notes.md").time, "10:00--10:30 EDT");
  assert.equal(fs.readFileSync(path.join(root, "md", "notes.md"), "utf-8"), "# Hi\n");

  const data = await api.loadFile("notes.md");
  assert.equal(data.markdown, "# Hi\n");
  // tz_hint is re-parsed from "time" on load; it's only ever used when no
  // real timezone is picked, so it doesn't change what gets saved.
  assert.deepEqual(data.header, { ...HEADER, tz_hint: "EDT" });
  assert.equal(data.pdf, null);
});

test("createFile sanitizes; deleteFile removes", async (t) => {
  const { api } = setup(t);
  assert.deepEqual(await api.createFile("Team Sync!"), { file: "Team-Sync.md", files: ["Team-Sync.md", "notes.md"] });
  assert.deepEqual(await api.deleteFile("Team-Sync.md"), { files: ["notes.md"] });
});

test("deleting the last file is refused", async (t) => {
  const { api } = setup(t);
  await assert.rejects(api.deleteFile("notes.md"), /last remaining/);
});

test("any filename outside md/'s own list is refused, not read or written", async (t) => {
  const { api } = setup(t);
  for (const name of ["missing.md", "../yaml/notes.yaml"]) {
    await assert.rejects(api.loadFile(name), PipelineError);
    await assert.rejects(api.saveFile(name, { header: HEADER, markdown: "x" }), PipelineError);
    await assert.rejects(api.renderFile(name, { header: HEADER, markdown: "x" }), PipelineError);
  }
});

test("renderFile saves first, then skips the build when topic/date are blank", async (t) => {
  const { api } = setup(t);
  const result = await api.renderFile("notes.md", { header: { ...HEADER, topic: "", date: "" }, markdown: "x" });
  assert.equal(result.ok, false);
  assert.equal(result.saved, true);
  assert.match(result.log, /topic and date/);
});

test("renderFile builds in this window's own build/app-<id> directory", async (t) => {
  const { root, api } = setup(t);
  const pdf = path.join(root, "pdf", "out.pdf");
  const calls = [];
  api.pipeline.render = async (filename, builddir) => {
    calls.push([filename, builddir]);
    fs.writeFileSync(pdf, "%PDF-1.4");
    return { success: true, log: "log", pdfPath: pdf };
  };
  const result = await api.renderFile("notes.md", { header: HEADER, markdown: "x" });
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "notes.md");
  assert.match(calls[0][1], /^build\/app-[0-9a-f]{32}$/);
  assert.equal(result.ok, true);
  assert.equal(result.pdf.name, "out.pdf");
  assert.equal(result.pdf.url, pathToFileURL(pdf).href);
  assert.equal(api.pdfPath("out.pdf"), pdf);
});

test("pdfPath only names files directly inside pdf/", (t) => {
  const { api } = setup(t);
  for (const name of ["../md/notes.md", "missing.pdf", "notes.md", 5]) {
    assert.throws(() => api.pdfPath(name), PipelineError);
  }
});

test("stale build/app-* dirs are pruned on startup, and cleanup() removes this window's own", (t) => {
  const root = makeProject(t);
  const stale = path.join(root, "build", "app-old");
  const keep = path.join(root, "build", "example");
  fs.mkdirSync(stale, { recursive: true });
  fs.mkdirSync(keep);
  const api = new Api({ projectRoot: root, repoRoot: REPO_ROOT });
  assert.ok(!fs.existsSync(stale));
  assert.ok(fs.existsSync(keep));

  const own = path.join(root, api.buildDir);
  fs.mkdirSync(own, { recursive: true });
  api.cleanup();
  assert.ok(!fs.existsSync(own));
});

test("asset lifecycle: upload, folder create/rename, move, delete", async (t) => {
  const { root, api } = setup(t);
  let data = await api.uploadAssets("", [{ name: "tux.png", data: new Uint8Array([112, 110, 103]) }]);
  assert.deepEqual(data.errors, []);
  assert.deepEqual(data.files, [
    { name: "tux.png", url: pathToFileURL(path.join(root, "assets", "tux.png")).href, size: 3, image: true },
  ]);

  await api.createAssetFolder("", "img");
  data = await api.renameAssetFolder("", "img", "pics");
  assert.deepEqual(data.folders, ["pics"]);

  data = await api.moveAssets("", ["tux.png"], "pics");
  assert.deepEqual(data.errors, []);
  assert.deepEqual(data.all_files, ["pics/tux.png"]);

  data = await api.deleteAsset("pics", "tux.png");
  assert.deepEqual(data.files, []);
  data = await api.deleteAssetFolder("", "pics");
  assert.deepEqual(data.folders, []);
});

test("upload/move report per-file errors without failing the rest", async (t) => {
  const { api } = setup(t);
  await api.uploadAssets("", [{ name: "a.txt", data: new Uint8Array([1]) }]);
  const data = await api.uploadAssets("", [
    { name: "a.txt", data: new Uint8Array([2]) },
    { name: "b.txt", data: new Uint8Array([3]) },
    { name: "c.txt", data: "not bytes" },
  ]);
  assert.equal(data.errors.length, 2);
  assert.deepEqual(data.all_files, ["a.txt", "b.txt"]);
});

test("deleting folder '..' is refused and leaves the project alone", async (t) => {
  const { root, api } = setup(t);
  await assert.rejects(api.deleteAssetFolder("", ".."), PipelineError);
  assert.ok(fs.existsSync(path.join(root, "md")));
});

test("wrong-typed arguments are refused with a PipelineError", async (t) => {
  const { api } = setup(t);
  await assert.rejects(api.createAssetFolder(5, "x"), /Expected a string for 'dir'/);
  await assert.rejects(api.saveFile("notes.md", { header: [], markdown: "x" }), /Expected a header object/);
  await assert.rejects(api.saveFile("notes.md", null), PipelineError);
  await assert.rejects(api.moveAssets("", "tux.png", ""), /Expected a list of names/);
});

test("every IPC channel names an Api method", () => {
  for (const name of CHANNELS) assert.equal(typeof Api.prototype[name], "function", name);
});
