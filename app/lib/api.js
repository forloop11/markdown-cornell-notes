// The editor's backend: every operation the renderer can ask for (see
// ../preload.js), as plain async methods over a Pipeline. main.js exposes
// each one as an IPC channel; keeping them free of Electron means the
// tests (../test/) can drive them directly.
//
// Everything here takes renderer-supplied values, which can't be trusted to
// have the right shape -- the str()/obj() checks below turn a wrong type
// into a PipelineError rather than a crash or an odd coercion.
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { pathToFileURL } = require("node:url");

const headerForm = require("./header-form");
const { Pipeline, PipelineError } = require("./pipeline");

// The editor/PDF pane height in pixels at the pane-height dropdown's "100%".
// Deliberately shorter than a full-width, letter-size page (aspect ratio
// 11/8.5 ~= 1.29 -- see settings/page.yaml's `paper`), so both panes fit
// comfortably on screen; the PDF frame still fills its full width via
// #view=FitH (see renderer/app.js), just with some scrolling needed to see
// the bottom of the page.
const BASE_PANE_HEIGHT = 600;

// Offered next to the Render button so the editor/PDF panes can be shrunk
// (e.g. on a smaller window) or grown beyond BASE_PANE_HEIGHT's default.
const PANE_HEIGHT_OPTIONS = Array.from({ length: 18 }, (_, i) => `${30 + i * 10}%`);

const IMAGE_SUFFIXES = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]);

function str(value, key) {
  if (typeof value !== "string") throw new PipelineError(`Expected a string for '${key}'.`);
  return value;
}

function obj(value, what) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new PipelineError(`Expected ${what}.`);
  }
  return value;
}

class Api {
  constructor({ projectRoot, repoRoot, tools }) {
    this.pipeline = new Pipeline({ projectRoot, repoRoot, tools });
    // Keys this window's own BUILDDIR (see render) so two app windows
    // rendering around the same time never race on the same scratch
    // directory.
    this.buildDir = `build/app-${crypto.randomUUID().replace(/-/g, "")}`;
    if (this.pipeline.projectInitialized()) this.pruneStaleBuildDirs();
  }

  // Remove build/app-<id> directories left over from a previous run (see
  // buildDir). Called once at startup, before this run has rendered
  // anything, so any app-* here must be stale.
  pruneStaleBuildDirs() {
    const buildRoot = path.join(this.pipeline.projectRoot, "build");
    if (!fs.existsSync(buildRoot)) return;
    for (const entry of fs.readdirSync(buildRoot, { withFileTypes: true })) {
      if (entry.isDirectory() && entry.name.startsWith("app-")) {
        fs.rmSync(path.join(buildRoot, entry.name), { recursive: true, force: true });
      }
    }
  }

  // Remove this window's own build directory (on window close).
  cleanup() {
    fs.rmSync(path.join(this.pipeline.projectRoot, this.buildDir), { recursive: true, force: true });
  }

  config() {
    return {
      initialized: this.pipeline.projectInitialized(),
      projectRoot: this.pipeline.projectRoot,
      basePaneHeight: BASE_PANE_HEIGHT,
      paneHeightOptions: PANE_HEIGHT_OPTIONS,
      tzOptions: headerForm.TZ_OPTIONS,
    };
  }

  // Scaffold a new project in projectRoot (the "no project" screen's "Set
  // up a project here" button), returning the updated config().
  async initProject() {
    this.pipeline.initProject();
    return this.config();
  }

  // {name, url, version} for an existing PDF at `file`, else null.
  // `version` (the file's mtime) lets the renderer bust its cache after a
  // re-render. URLs are built here because the sandboxed renderer can't
  // turn a filesystem path into one itself.
  pdfInfo(file) {
    const stat = file && fs.statSync(file, { throwIfNoEntry: false });
    if (!stat || !stat.isFile()) return null;
    return { name: path.basename(file), url: pathToFileURL(file).href, version: Math.floor(stat.mtimeMs) };
  }

  // pdfInfo for the PDF `filename`'s current header would build to, if
  // that PDF already exists on disk.
  async existingPdf(filename) {
    try {
      const slug = await this.pipeline.topicSlug(this.pipeline.yamlPathFor(filename));
      return this.pdfInfo(path.join(this.pipeline.pdfDir, `${slug}.pdf`));
    } catch (err) {
      if (err instanceof PipelineError) return null;
      throw err;
    }
  }

  checkMarkdownFile(filename) {
    if (!this.pipeline.listMarkdownFiles().includes(filename)) throw new PipelineError(`${filename} not found.`);
  }

  // Write the header form and markdown in `body` to filename's yaml/md
  // files, returning the stored header fields.
  save(filename, body) {
    obj(body, "a JSON object");
    const fields = headerForm.headerFromForm(obj(body.header, "a header object"));
    const markdown = str(body.markdown, "markdown");
    this.pipeline.writeHeader(filename, fields);
    this.pipeline.writeMarkdownFile(filename, markdown);
    return fields;
  }

  // --- Markdown files ---------------------------------------------------

  async listFiles() {
    return { files: this.pipeline.listMarkdownFiles() };
  }

  async createFile(name) {
    const file = this.pipeline.createMarkdownFile(str(name, "name"));
    return { file, files: this.pipeline.listMarkdownFiles() };
  }

  async loadFile(filename) {
    this.checkMarkdownFile(filename);
    return {
      name: filename,
      header: headerForm.formFromHeader(this.pipeline.readHeader(filename)),
      markdown: this.pipeline.readMarkdownFile(filename),
      pdf: await this.existingPdf(filename),
    };
  }

  // Autosave target: the renderer calls this whenever the header or
  // markdown changes (debounced), so closing the window between renders
  // doesn't lose what was typed.
  async saveFile(filename, body) {
    this.checkMarkdownFile(filename);
    try {
      this.save(filename, body);
    } catch (err) {
      if (err instanceof PipelineError) throw err;
      throw new PipelineError(`Couldn't autosave ${filename}: ${err.message}`);
    }
    return { ok: true };
  }

  async deleteFile(filename) {
    this.pipeline.deleteMarkdownFile(filename);
    return { files: this.pipeline.listMarkdownFiles() };
  }

  // Save the sent header/markdown, then build filename's PDF. The content
  // is exactly what's in the editor at the moment Render was clicked, so
  // the build never runs against a stale save.
  async renderFile(filename, body) {
    this.checkMarkdownFile(filename);
    let fields;
    try {
      fields = this.save(filename, body);
    } catch (err) {
      if (err instanceof PipelineError) throw err;
      return { ok: false, saved: false, log: `Render skipped: couldn't save changes to disk.\n${err.message}`, pdf: null };
    }

    const missing = ["topic", "date"].filter((name) => !fields[name].trim());
    if (missing.length) {
      return {
        ok: false,
        saved: true,
        log:
          `Render skipped: ${missing.join(" and ")} field(s) empty.\n` +
          "Fill in the header before rendering, or the output PDF's name " +
          "and header row will end up mostly blank.",
        pdf: null,
      };
    }

    const { success, log, pdfPath } = await this.pipeline.render(filename, this.buildDir);
    return { ok: success, saved: true, log, pdf: this.pdfInfo(pdfPath) };
  }

  // The path of built PDF `name` in pdf/ (for "Download PDF"'s copy).
  pdfPath(name) {
    str(name, "name");
    if (path.basename(name) !== name || !name.endsWith(".pdf")) throw new PipelineError(`Invalid name: ${name}.`);
    const file = path.join(this.pipeline.pdfDir, name);
    if (!fs.existsSync(file)) throw new PipelineError(`${name} not found.`);
    return file;
  }

  // --- Assets -------------------------------------------------------------

  // Everything the Assets panel and the editor's path autocompletion need
  // for folder assets/<subdir>.
  assetListing(subdir, extra = {}) {
    const { folders, files } = this.pipeline.listAssetDir(subdir);
    const base = this.pipeline.resolveAssetDir(subdir);
    return {
      ...extra,
      dir: subdir,
      folders,
      files: files.map((name) => {
        const file = path.join(base, name);
        return {
          name,
          url: pathToFileURL(file).href,
          size: fs.statSync(file).size,
          image: IMAGE_SUFFIXES.has(path.extname(name).toLowerCase()),
        };
      }),
      folder_paths: this.pipeline.listAssetFolderPaths(),
      all_files: this.pipeline.listAssetFiles(),
    };
  }

  async listAssets(dir = "") {
    return this.assetListing(str(dir, "dir"));
  }

  // `uploads` is [{name, data}] with data a Uint8Array of the file's bytes.
  async uploadAssets(dir, uploads) {
    str(dir, "dir");
    if (!Array.isArray(uploads)) throw new PipelineError("Expected a list of files.");
    const errors = [];
    for (const upload of uploads) {
      try {
        obj(upload, "a file");
        if (!(upload.data instanceof Uint8Array)) throw new PipelineError("Expected file contents.");
        this.pipeline.saveAsset(str(upload.name, "name"), upload.data, dir);
      } catch (err) {
        if (!(err instanceof PipelineError)) throw err;
        errors.push(err.message);
      }
    }
    return this.assetListing(dir, { errors });
  }

  async createAssetFolder(dir, name) {
    this.pipeline.createAssetFolder(str(name, "name"), str(dir, "dir"));
    return this.assetListing(dir);
  }

  async renameAssetFolder(dir, name, newName) {
    this.pipeline.renameAssetFolder(str(name, "name"), str(newName, "new_name"), str(dir, "dir"));
    return this.assetListing(dir);
  }

  async deleteAssetFolder(dir, name) {
    this.pipeline.deleteAssetFolder(str(name, "name"), str(dir, "dir"));
    return this.assetListing(dir);
  }

  async deleteAsset(dir, name) {
    this.pipeline.deleteAsset(str(name, "name"), str(dir, "dir"));
    return this.assetListing(dir);
  }

  async moveAssets(dir, names, dest) {
    str(dir, "dir");
    str(dest, "dest");
    if (!Array.isArray(names)) throw new PipelineError("Expected a list of names.");
    const errors = [];
    for (const name of names) {
      try {
        this.pipeline.moveAsset(name, dir, dest);
      } catch (err) {
        if (!(err instanceof PipelineError)) throw err;
        errors.push(err.message);
      }
    }
    return this.assetListing(dir, { errors });
  }
}

// The Api methods the renderer may call, one IPC channel each (see main.js
// and preload.js). Anything not listed here -- helpers like save() or
// pdfPath() -- stays main-process only.
const CHANNELS = [
  "config",
  "initProject",
  "listFiles",
  "createFile",
  "loadFile",
  "saveFile",
  "deleteFile",
  "renderFile",
  "listAssets",
  "uploadAssets",
  "createAssetFolder",
  "renameAssetFolder",
  "deleteAssetFolder",
  "deleteAsset",
  "moveAssets",
];

module.exports = { Api, CHANNELS, PipelineError };
