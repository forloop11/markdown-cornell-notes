// Shared setup for the app's tests: an isolated md/yaml/pdf/assets project
// in a temp directory, so tests never touch the real repo's md/, yaml/,
// pdf/, or assets/.
"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");

// A fresh project directory, removed again when the calling test ends.
function makeProject(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "mcn-test-"));
  for (const name of ["md", "yaml", "pdf", "assets"]) fs.mkdirSync(path.join(root, name));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

module.exports = { REPO_ROOT, makeProject };
