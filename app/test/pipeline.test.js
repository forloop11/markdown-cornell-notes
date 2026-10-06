// Tests for lib/pipeline.js, run against an isolated project (see
// helpers.js). render() itself needs the full pandoc/TeX Live toolchain,
// so it isn't covered here; topicSlug() is, since it only needs python3.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const { Pipeline, PipelineError, HEADER_FIELDS } = require("../lib/pipeline");
const { REPO_ROOT, makeProject } = require("./helpers");

const blank = () => Object.fromEntries(HEADER_FIELDS.map((f) => [f, ""]));

function setup(t) {
  const root = makeProject(t);
  return { root, p: new Pipeline({ projectRoot: root, repoRoot: REPO_ROOT }) };
}

test("projectInitialized() is true once md/ and yaml/ exist, false before", (t) => {
  const { root, p } = setup(t);
  assert.ok(p.projectInitialized());
  fs.rmSync(path.join(root, "md"), { recursive: true });
  assert.ok(!p.projectInitialized());
});

test("yamlPathFor() pairs md/<stem>.md with yaml/<stem>.yaml", (t) => {
  const { root, p } = setup(t);
  assert.equal(p.yamlPathFor("weekly-sync.md"), path.join(root, "yaml", "weekly-sync.yaml"));
});

test("readHeader() on a file with no paired yaml returns every field blank", (t) => {
  const { p } = setup(t);
  assert.deepEqual(p.readHeader("does-not-exist.md"), blank());
});

test("writeHeader() then readHeader() round-trips", (t) => {
  const { p } = setup(t);
  const fields = {
    topic: "Weekly Sync",
    date: "2026-08-23",
    attendees: "Lily, Amber",
    time: "10:00--10:30 EDT",
    timezone: "America/Detroit",
    location: "Zoom",
  };
  p.writeHeader("notes.md", fields);
  assert.deepEqual(p.readHeader("notes.md"), fields);
});

test('writeHeader() escapes " and \\ so they survive the round-trip', (t) => {
  const { p } = setup(t);
  const fields = { ...blank(), topic: 'Say "hi" \\ok', location: "C:\\path" };
  p.writeHeader("notes.md", fields);
  assert.deepEqual(p.readHeader("notes.md"), fields);
});

test("the build scripts' own yaml parser reads what writeHeader() wrote", (t) => {
  // simple_yaml.py, not pipeline.js, is what `make build` reads headers
  // with -- the two must agree on escaping.
  const { p } = setup(t);
  const topic = 'Say "hi" \\ok';
  p.writeHeader("notes.md", { ...blank(), topic });
  const out = execFileSync(
    "python3",
    ["-c", "import sys, json; from simple_yaml import parse_yaml; print(json.dumps(parse_yaml(sys.argv[1])))", p.yamlPathFor("notes.md")],
    { cwd: path.join(REPO_ROOT, "scripts"), encoding: "utf-8" }
  );
  assert.equal(JSON.parse(out).topic, topic);
});

test("create/list/read/delete a markdown file and its paired yaml", (t) => {
  const { p } = setup(t);
  const created = p.createMarkdownFile("My Notes!");
  assert.equal(created, "My-Notes.md");
  assert.ok(p.listMarkdownFiles().includes(created));
  assert.equal(p.readMarkdownFile(created), "# New notes\n");
  assert.deepEqual(p.readHeader(created), blank());

  // A second file, so deleting the first isn't blocked by the last-file guard.
  p.createMarkdownFile("other");
  p.deleteMarkdownFile(created);
  assert.ok(!p.listMarkdownFiles().includes(created));
  assert.ok(!fs.existsSync(p.yamlPathFor(created)));
});

test("createMarkdownFile() refuses duplicates and blank names", (t) => {
  const { p } = setup(t);
  p.createMarkdownFile("dup");
  assert.throws(() => p.createMarkdownFile("dup"), PipelineError);
  assert.throws(() => p.createMarkdownFile("   "), PipelineError);
});

test("createMarkdownFile() drops directory parts and slugifies the rest", (t) => {
  const { p } = setup(t);
  assert.equal(p.createMarkdownFile("a/b?c*d"), "b-c-d.md");
  assert.equal(p.createMarkdownFile("notes.md"), "notes.md");
});

test("deleteMarkdownFile() refuses the last file and unknown names", (t) => {
  const { p } = setup(t);
  const only = p.createMarkdownFile("only");
  assert.throws(() => p.deleteMarkdownFile(only), PipelineError);
  assert.throws(() => p.deleteMarkdownFile("nope.md"), PipelineError);
});

test("writeMarkdownFile() then readMarkdownFile() round-trips", (t) => {
  const { p } = setup(t);
  p.createMarkdownFile("notes");
  p.writeMarkdownFile("notes.md", "hello world\n");
  assert.equal(p.readMarkdownFile("notes.md"), "hello world\n");
});

for (const name of ["../yaml/notes.yaml", "..", "missing.md", "notes.txt"]) {
  test(`read/writeMarkdownFile() refuse ${JSON.stringify(name)}`, (t) => {
    const { root, p } = setup(t);
    p.createMarkdownFile("notes");
    fs.writeFileSync(path.join(root, "md", "notes.txt"), "x");
    assert.throws(() => p.readMarkdownFile(name), PipelineError);
    assert.throws(() => p.writeMarkdownFile(name, "overwritten"), PipelineError);
    assert.notEqual(fs.readFileSync(path.join(root, "yaml", "notes.yaml"), "utf-8"), "overwritten");
  });
}

test("topicSlug() joins slugified topic/date/location", async (t) => {
  const { p } = setup(t);
  p.writeHeader("notes.md", { ...blank(), topic: "Weekly Sync", date: "2026-08-23", location: "Zoom" });
  assert.equal(await p.topicSlug(p.yamlPathFor("notes.md")), "Weekly-Sync_2026-08-23_Zoom");
});

test('topicSlug() falls back to "cornell-notes" when all fields are blank', async (t) => {
  const { p } = setup(t);
  p.writeHeader("notes.md", blank());
  assert.equal(await p.topicSlug(p.yamlPathFor("notes.md")), "cornell-notes");
});

test("asset folders: create, rename, nest, delete with contents", (t) => {
  const { p } = setup(t);
  p.createAssetFolder("diagrams");
  assert.deepEqual(p.listAssetDir(), { folders: ["diagrams"], files: [] });
  assert.throws(() => p.createAssetFolder("diagrams"), PipelineError);

  p.createAssetFolder("flowcharts", "diagrams");
  assert.deepEqual(p.listAssetFolderPaths(), ["", "diagrams", "diagrams/flowcharts"]);

  assert.equal(p.renameAssetFolder("diagrams", "new name!"), "new-name");
  assert.deepEqual(p.listAssetDir().folders, ["new-name"]);

  p.saveAsset("flow.png", Buffer.from("png"), "new-name");
  p.deleteAssetFolder("new-name");
  assert.deepEqual(p.listAssetDir().folders, []);
});

test("asset files: save, list, refuse duplicates, move, delete", (t) => {
  const { p } = setup(t);
  p.saveAsset("tux.jpg", Buffer.from("one"));
  assert.deepEqual(p.listAssetFiles(), ["tux.jpg"]);
  assert.throws(() => p.saveAsset("tux.jpg", Buffer.from("two")), PipelineError);

  p.createAssetFolder("dest");
  p.saveAsset("tux.jpg", Buffer.from("two"), "dest");
  assert.throws(() => p.moveAsset("tux.jpg", "", "dest"), PipelineError);
  p.deleteAsset("tux.jpg", "dest");
  p.moveAsset("tux.jpg", "", "dest");
  assert.deepEqual(p.listAssetFiles(), ["dest/tux.jpg"]);

  assert.throws(() => p.deleteAsset("nope.jpg"), PipelineError);
});

test("saveAsset() drops directory parts from the file name", (t) => {
  const { root, p } = setup(t);
  assert.equal(p.saveAsset("../../etc/passwd", Buffer.from("data")), "passwd");
  assert.ok(fs.existsSync(path.join(root, "assets", "passwd")));
  assert.ok(!fs.existsSync(path.join(root, "etc")));
});

test("a subdir outside assets/ is refused", (t) => {
  const { p } = setup(t);
  assert.throws(() => p.createAssetFolder("evil", "../../../../etc"), PipelineError);
});

test("a symlinked folder leading outside assets/ is refused", (t) => {
  const { root, p } = setup(t);
  fs.mkdirSync(path.join(root, "outside"));
  fs.symlinkSync(path.join(root, "outside"), path.join(root, "assets", "link"));
  assert.throws(() => p.saveAsset("x.txt", Buffer.from("x"), "link"), PipelineError);
});

for (const name of ["..", ".", "", "../outside", "sub/file.jpg", "..\\outside"]) {
  test(`asset entry name ${JSON.stringify(name)} can't escape its folder`, (t) => {
    // Deleting folder ".." would otherwise remove the whole project.
    const { root, p } = setup(t);
    fs.mkdirSync(path.join(root, "outside"));
    for (const call of [
      () => p.deleteAsset(name),
      () => p.deleteAssetFolder(name),
      () => p.renameAssetFolder(name, "renamed"),
      () => p.moveAsset(name, "", ""),
    ]) {
      assert.throws(call, PipelineError);
    }
    assert.ok(fs.existsSync(path.join(root, "outside")));
    assert.ok(fs.existsSync(path.join(root, "md")));
  });
}
