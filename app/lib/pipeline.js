// Thin wrapper around the Cornell notes CLI pipeline (see ../../Makefile)
// for the Electron app: header read/write, markdown file management, and
// building the PDF -- via `make build`, or (on Windows, which has no make
// or Unix shell) by running the same steps directly; see render().
//
// File, folder, and asset names passed in here come straight from the
// renderer (see api.js), so every method that takes one checks it can't
// escape its own directory (see checkPlainName) rather than trusting the
// caller.
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { execFile } = require("node:child_process");

const HEADER_FIELDS = ["topic", "date", "attendees", "time", "timezone", "location"];

const HEADER_COMMENT =
  "# Header details for the first \\cornellpage in settings/template.tex.\n" +
  "# Run `python3 scripts/yaml_to_header.py` to regenerate build/cornell-header.tex, then\n" +
  "# compile settings/template.tex with pdflatex as usual.\n";

const SAFE_STEM_RE = /[^A-Za-z0-9._-]+/g;

// A user-facing error from this module (e.g. a name collision or an invalid
// path) -- api.js passes its message straight to the renderer, unlike an
// unexpected exception.
class PipelineError extends Error {}

// Python's Path(name).name: the last non-empty, non-"." component.
function baseName(name) {
  const parts = name.split("/").filter((p) => p && p !== ".");
  return parts.length ? parts[parts.length - 1] : "";
}

// Python's Path(name).stem: baseName minus its last ".suffix" (a leading
// dot, as in ".hidden", isn't a suffix).
function stemOf(name) {
  const base = baseName(name);
  const dot = base.lastIndexOf(".");
  return dot > 0 && dot < base.length - 1 ? base.slice(0, dot) : base;
}

// Collapse unsafe characters to "-" and strip leading/trailing "-".
const slugify = (value) => value.replace(SAFE_STEM_RE, "-").replace(/^-+|-+$/g, "");

// Raise PipelineError unless `name` is a single path component (no "/" or
// "\\" separators, and not "", "." or "..") -- i.e. something that, joined
// onto a directory, can only name an entry directly inside it.
function checkPlainName(name) {
  if (
    typeof name !== "string" ||
    name === "" ||
    name === "." ||
    name === ".." ||
    name.includes("/") ||
    name.includes("\\") ||
    name.includes("\0")
  ) {
    throw new PipelineError(`Invalid name: ${JSON.stringify(name)}.`);
  }
}

// Reverse the `\` -> `\\`, `"` -> `\"` escaping applied by writeHeader -- the
// same rule as scripts/simple_yaml.py's strip_quotes, which the build
// scripts use to read these files back.
function stripQuotes(value) {
  if (value.length >= 2 && value[0] === value[value.length - 1] && (value[0] === '"' || value[0] === "'")) {
    const inner = value.slice(1, -1);
    return value[0] === '"' ? inner.replace(/\\([\\"])/g, "$1") : inner;
  }
  return value;
}

// Parse a flat "key: value" yaml file -- the same subset (and comment
// handling) as scripts/simple_yaml.py's parse_yaml.
function parseYaml(file) {
  const fields = {};
  fs.readFileSync(file, "utf-8")
    .split(/\r?\n/)
    .forEach((rawLine, i) => {
      const line = rawLine.split("#", 1)[0].trim();
      if (!line) return;
      const colon = line.indexOf(":");
      if (colon === -1) throw new Error(`${file}:${i + 1}: expected 'key: value', got: ${JSON.stringify(rawLine)}`);
      fields[line.slice(0, colon).trim()] = stripQuotes(line.slice(colon + 1).trim());
    });
  return fields;
}

const byCodePoint = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

const isDir = (p) => fs.statSync(p, { throwIfNoEntry: false })?.isDirectory() ?? false;
const isFile = (p) => fs.statSync(p, { throwIfNoEntry: false })?.isFile() ?? false;

// Every entry under `dir`, recursively, as paths relative to it -- not
// following symlinked directories, so a link can't loop or lead outside.
function walk(dir, rel = "") {
  const out = [];
  for (const entry of fs.readdirSync(path.join(dir, rel), { withFileTypes: true })) {
    const relPath = rel ? `${rel}/${entry.name}` : entry.name;
    out.push(relPath);
    if (entry.isDirectory()) out.push(...walk(dir, relPath));
  }
  return out;
}

// The files `make init` copies into a fresh project: [source under
// repoRoot, destination under projectRoot].
const INIT_FILES = [
  ["md/notes-example.md", "md/notes.md"],
  ["yaml/notes-example.yaml", "yaml/notes.yaml"],
  ["settings/page.yaml", "settings/page.yaml"],
  ["assets/tux.jpg", "assets/tux.jpg"],
];
const INIT_DIRS = ["md", "yaml", "settings", "pdf", "assets"];

// pdflatex log lines asking for another pass (cross-references, longtable
// column widths, hyperref's outlines via rerunfilecheck) -- what latexmk
// watches for when deciding to rerun.
const RERUN_RE = /Rerun to get|Label\(s\) may have changed|Table widths have changed/;
const MAX_LATEX_PASSES = 4;

// The pdflatex auxiliary files `latexmk -c` would remove after a build.
const LATEX_AUX_SUFFIXES = [".aux", ".log", ".out", ".toc", ".fls", ".fdb_latexmk"];

class Pipeline {
  // repoRoot is where the pipeline itself (scripts/, the Makefile) lives,
  // which for an installed package is the read-only
  // /usr/share/markdown-cornell-notes tree. projectRoot is the user's
  // actual project -- the directory the app was launched from, matching
  // `make app`/the installed CLI's "operate on CWD" model (see Makefile's
  // MCN_ROOT). md/, yaml/, pdf/, assets/ are project data and live under
  // projectRoot.
  //
  // `tools` says how to reach the build's helper programs: `python` is the
  // interpreter to run scripts/ with, `pathDirs` are prepended to PATH
  // (e.g. bundled pandoc and TeX directories in the Windows build -- see
  // main.js), and `directBuild` runs the build steps here instead of via
  // `make` (always the case on Windows).
  constructor({ projectRoot, repoRoot = path.resolve(__dirname, "..", ".."), tools = {} }) {
    this.projectRoot = path.resolve(projectRoot);
    this.repoRoot = repoRoot;
    const windows = process.platform === "win32";
    this.tools = {
      python: tools.python || (windows ? "python" : "python3"),
      pathDirs: tools.pathDirs || [],
      directBuild: tools.directBuild ?? (windows || process.env.MCN_DIRECT_BUILD === "1"),
    };
    this.scriptsDir = path.join(repoRoot, "scripts");
    this.mdDir = path.join(this.projectRoot, "md");
    this.yamlDir = path.join(this.projectRoot, "yaml");
    this.pdfDir = path.join(this.projectRoot, "pdf");
    this.assetsDir = path.join(this.projectRoot, "assets");
  }

  // Whether projectRoot looks like a scaffolded project (see `make init`)
  // -- md/ and yaml/ must exist before any read/write below is safe.
  projectInitialized() {
    return isDir(this.mdDir) && isDir(this.yamlDir);
  }

  // Scaffold a fresh project in projectRoot from the bundled defaults --
  // the same checks and files as the Makefile's `init` target.
  initProject() {
    if (path.resolve(this.projectRoot) === path.resolve(this.repoRoot)) {
      throw new PipelineError("Already in the markdown-cornell-notes source tree; nothing to init.");
    }
    for (const dir of INIT_DIRS) {
      if (fs.existsSync(path.join(this.projectRoot, dir))) {
        throw new PipelineError(`Refusing to init: '${dir}' already exists in ${this.projectRoot}.`);
      }
    }
    for (const dir of INIT_DIRS) fs.mkdirSync(path.join(this.projectRoot, dir), { recursive: true });
    for (const [from, to] of INIT_FILES) {
      fs.copyFileSync(path.join(this.repoRoot, from), path.join(this.projectRoot, to));
    }
  }

  // The environment for helper programs: this process's, with
  // tools.pathDirs prepended to PATH. (Windows spells it "Path", and
  // treats it case-insensitively -- reuse whichever key is there rather
  // than adding a second one.) PYTHONUTF8 keeps Python's own I/O UTF-8
  // regardless of the Windows code page.
  childEnv() {
    const env = { ...process.env, PYTHONUTF8: "1" };
    if (this.tools.pathDirs.length) {
      const key = Object.keys(env).find((k) => k.toUpperCase() === "PATH") || "PATH";
      env[key] = [...this.tools.pathDirs, env[key]].filter(Boolean).join(path.delimiter);
    }
    return env;
  }

  // Run one of scripts/ with tools.python, from projectRoot.
  runScript(script, args) {
    return run(this.tools.python, [path.join(this.scriptsDir, script), ...args], {
      cwd: this.projectRoot,
      env: this.childEnv(),
    });
  }

  // The header yaml paired with a markdown file: md/<stem>.md <-> yaml/<stem>.yaml.
  yamlPathFor(mdFilename) {
    return path.join(this.yamlDir, `${stemOf(mdFilename)}.yaml`);
  }

  // mdFilename's paired header, with every HEADER_FIELDS name ("" if the
  // yaml doesn't exist, or doesn't set that field).
  readHeader(mdFilename) {
    const file = this.yamlPathFor(mdFilename);
    const fields = isFile(file) ? parseYaml(file) : {};
    return Object.fromEntries(HEADER_FIELDS.map((name) => [name, fields[name] ?? ""]));
  }

  // Write `fields` to mdFilename's paired header yaml, quoting and escaping
  // each value.
  writeHeader(mdFilename, fields) {
    const lines = [HEADER_COMMENT.replace(/\n+$/, ""), ""];
    for (const name of HEADER_FIELDS) {
      // Backslash first, then quote -- otherwise a value containing a
      // literal backslash would corrupt the quote-escaping below (and,
      // since stripQuotes/simple_yaml.py unescape in the same order, doing
      // it any other way here would break the round-trip).
      const value = (fields[name] ?? "").replace(/\\/g, "\\\\").replace(/"/g, '\\"');
      lines.push(`${name}: "${value}"`);
    }
    fs.writeFileSync(this.yamlPathFor(mdFilename), lines.join("\n") + "\n", "utf-8");
  }

  // All *.md filenames directly inside md/, sorted.
  listMarkdownFiles() {
    return fs
      .readdirSync(this.mdDir, { withFileTypes: true })
      .filter((e) => e.name.endsWith(".md") && isFile(path.join(this.mdDir, e.name)))
      .map((e) => e.name)
      .sort(byCodePoint);
  }

  // Create a new, blank markdown file (and its paired, blank header yaml)
  // named after the sanitized stem of `name`, returning the filename
  // actually used.
  createMarkdownFile(name) {
    const stem = slugify(stemOf(String(name)).trim());
    if (!stem) throw new PipelineError("File name can't be empty.");
    const filename = `${stem}.md`;
    const file = path.join(this.mdDir, filename);
    if (fs.existsSync(file)) throw new PipelineError(`${filename} already exists.`);
    fs.writeFileSync(file, "# New notes\n", "utf-8");
    this.writeHeader(filename, Object.fromEntries(HEADER_FIELDS.map((f) => [f, ""])));
    return filename;
  }

  // Delete `name` (one of listMarkdownFiles()) and its paired header yaml.
  // Refuses to delete the last remaining markdown file.
  deleteMarkdownFile(name) {
    const files = this.listMarkdownFiles();
    if (!files.includes(name)) throw new PipelineError(`${name} not found.`);
    if (files.length <= 1) throw new PipelineError("Can't delete the last remaining markdown file.");
    fs.unlinkSync(path.join(this.mdDir, name));
    fs.rmSync(this.yamlPathFor(name), { force: true });
  }

  // md/<name>, for an existing markdown file `name`.
  markdownPath(name) {
    checkPlainName(name);
    const file = path.join(this.mdDir, name);
    if (!name.endsWith(".md") || !isFile(file)) throw new PipelineError(`${name} not found.`);
    return file;
  }

  readMarkdownFile(name) {
    return fs.readFileSync(this.markdownPath(name), "utf-8");
  }

  // Overwrite md/<name> (which must already exist) with `content`.
  writeMarkdownFile(name, content) {
    fs.writeFileSync(this.markdownPath(name), content, "utf-8");
  }

  // All files under assets/, recursively, as paths relative to assets/
  // (e.g. "diagrams/flow.png") -- for the editor's link/image
  // autocompletion and the Assets panel's file count.
  listAssetFiles() {
    if (!isDir(this.assetsDir)) return [];
    return walk(this.assetsDir)
      .filter((rel) => isFile(path.join(this.assetsDir, rel)))
      .sort(byCodePoint);
  }

  // Resolve a folder path within assets/, guarding against escaping it
  // (e.g. a subdir of "../../etc", or a symlink pointing outside).
  resolveAssetDir(subdir = "") {
    if (!subdir) return this.assetsDir;
    if (typeof subdir !== "string") throw new PipelineError("Invalid folder path.");
    const inside = (p, root) => p === root || p.startsWith(root + path.sep);
    const resolved = path.resolve(this.assetsDir, subdir);
    if (!inside(resolved, this.assetsDir)) throw new PipelineError("Invalid folder path.");
    if (fs.existsSync(resolved) && !inside(fs.realpathSync(resolved), fs.realpathSync(this.assetsDir))) {
      throw new PipelineError("Invalid folder path.");
    }
    return resolved;
  }

  // Folders and files directly inside assets/<subdir> (not recursive), as
  // two sorted name lists.
  listAssetDir(subdir = "") {
    const base = this.resolveAssetDir(subdir);
    if (!isDir(base)) return { folders: [], files: [] };
    const names = fs.readdirSync(base).sort(byCodePoint);
    return {
      folders: names.filter((n) => isDir(path.join(base, n))),
      files: names.filter((n) => isFile(path.join(base, n))),
    };
  }

  // Every folder under assets/, recursively, as slash-joined paths ("" for
  // assets/ itself) -- for the "move to folder" picker.
  listAssetFolderPaths() {
    if (!isDir(this.assetsDir)) return [""];
    return ["", ...walk(this.assetsDir).filter((rel) => isDir(path.join(this.assetsDir, rel))).sort(byCodePoint)];
  }

  // Write `data` as a new file named after the sanitized form of
  // `filename` inside assets/<subdir>, returning the name actually used.
  saveAsset(filename, data, subdir = "") {
    const safeName = sanitizeName(filename);
    const base = this.resolveAssetDir(subdir);
    const file = path.join(base, safeName);
    if (fs.existsSync(file)) throw new PipelineError(`${safeName} already exists in ${displayDir(subdir)}/.`);
    fs.writeFileSync(file, data);
    return safeName;
  }

  deleteAsset(name, subdir = "") {
    checkPlainName(name);
    const file = path.join(this.resolveAssetDir(subdir), name);
    if (!isFile(file)) throw new PipelineError(`${name} not found in ${displayDir(subdir)}/.`);
    fs.unlinkSync(file);
  }

  // Move assets/<srcSubdir>/<name> into assets/<destSubdir>/, keeping its name.
  moveAsset(name, srcSubdir, destSubdir) {
    checkPlainName(name);
    const src = path.join(this.resolveAssetDir(srcSubdir), name);
    const destBase = this.resolveAssetDir(destSubdir);
    if (!isFile(src)) throw new PipelineError(`${name} not found in ${displayDir(srcSubdir)}/.`);
    if (!isDir(destBase)) throw new PipelineError(`${displayDir(destSubdir)}/ not found.`);
    const dest = path.join(destBase, name);
    if (fs.existsSync(dest)) throw new PipelineError(`${name} already exists in ${displayDir(destSubdir)}/.`);
    fs.renameSync(src, dest);
  }

  createAssetFolder(name, subdir = "") {
    const folderName = sanitizeName(name);
    const dir = path.join(this.resolveAssetDir(subdir), folderName);
    if (fs.existsSync(dir)) throw new PipelineError(`${folderName} already exists in ${displayDir(subdir)}/.`);
    fs.mkdirSync(dir, { recursive: true });
    return folderName;
  }

  renameAssetFolder(oldName, newName, subdir = "") {
    checkPlainName(oldName);
    const base = this.resolveAssetDir(subdir);
    const oldPath = path.join(base, oldName);
    if (!isDir(oldPath)) throw new PipelineError(`${oldName} not found in ${displayDir(subdir)}/.`);
    const safeName = sanitizeName(newName);
    const newPath = path.join(base, safeName);
    if (newPath !== oldPath && fs.existsSync(newPath)) {
      throw new PipelineError(`${safeName} already exists in ${displayDir(subdir)}/.`);
    }
    fs.renameSync(oldPath, newPath);
    return safeName;
  }

  deleteAssetFolder(name, subdir = "") {
    checkPlainName(name);
    const dir = path.join(this.resolveAssetDir(subdir), name);
    if (!isDir(dir)) throw new PipelineError(`${name} not found in ${displayDir(subdir)}/.`);
    fs.rmSync(dir, { recursive: true });
  }

  // The output PDF's base filename (the latexmk jobname) for the header
  // yaml at `yamlPath`. Runs scripts/topic_slug.py -- the same script the
  // Makefile names the PDF with -- so the two can never disagree.
  async topicSlug(yamlPath) {
    const { code, stdout, stderr } = await this.runScript("topic_slug.py", [yamlPath]);
    if (code !== 0) throw new PipelineError(stderr.trim() || "Failed to compute output filename.");
    return stdout.trim();
  }

  // Run `make build` for `mdFilename`, in scratch BUILDDIR `builddir` (one
  // per app window, so it never collides with -- or goes stale against --
  // a manual `make build`/`make build-example` run from the CLI).
  //
  // Resolves to {success, log, pdfPath}. pdfPath is set even on failure
  // when it could still be resolved, so the caller can show the previous
  // PDF.
  //
  // Runs `make` against repoRoot's Makefile (the library copy -- read-only
  // when installed) but with projectRoot as the CWD, so MD/YAML/BUILDDIR
  // resolve against the user's project, the same as the `-f .../Makefile`
  // (no `-C`) invocation the installed CLI uses.
  async render(mdFilename, builddir) {
    const yamlPath = this.yamlPathFor(mdFilename);
    const { code, stdout, stderr } = this.tools.directBuild
      ? await this.buildDirect(mdFilename, yamlPath, builddir)
      : await this.buildWithMake(mdFilename, yamlPath, builddir);

    let pdfPath = null;
    try {
      const candidate = path.join(this.pdfDir, `${await this.topicSlug(yamlPath)}.pdf`);
      if (isFile(candidate)) pdfPath = candidate;
    } catch (err) {
      if (!(err instanceof PipelineError)) throw err;
    }
    return { success: code === 0, log: stdout + stderr, pdfPath };
  }

  buildWithMake(mdFilename, yamlPath, builddir) {
    return run(
      "make",
      [
        "-f",
        path.join(this.repoRoot, "Makefile"),
        "build",
        `MD=md/${mdFilename}`,
        `YAML=${path.relative(this.projectRoot, yamlPath)}`,
        `BUILDDIR=${builddir}`,
      ],
      { cwd: this.projectRoot, env: this.childEnv() }
    );
  }

  // The Makefile's `build` target, step by step, for platforms without
  // make (Windows): the same three scripts, then pdflatex -- rerun until
  // its log stops asking for another pass, as latexmk would -- then
  // latexmk -c's cleanup. Resolves to {code, stdout, stderr} like run(),
  // stopping at the first failing step.
  async buildDirect(mdFilename, yamlPath, builddir) {
    const rel = (p) => path.relative(this.projectRoot, p).split(path.sep).join("/");
    const settingsYaml = path.join(this.projectRoot, "settings", "page.yaml");
    const out = { code: 0, stdout: "", stderr: "" };
    const step = async (promise) => {
      const result = await promise;
      out.stdout += result.stdout;
      out.stderr += result.stderr;
      out.code = result.code;
      return result.code === 0;
    };

    if (!isFile(settingsYaml)) {
      return { code: 1, stdout: "", stderr: "settings/page.yaml not found -- set up the project first.\n" };
    }
    const buildDir = path.join(this.projectRoot, builddir);
    fs.mkdirSync(buildDir, { recursive: true });
    fs.mkdirSync(this.pdfDir, { recursive: true });
    // TeX and the scripts both get forward-slash paths relative to
    // projectRoot (their CWD).
    const texBuildDir = builddir.split(path.sep).join("/");
    const inBuild = (name) => `${texBuildDir}/${name}`;

    if (!(await step(this.runScript("yaml_to_header.py", [rel(yamlPath), inBuild("cornell-header.tex")])))) return out;
    if (
      !(await step(
        this.runScript("markdown_to_pages.py", [
          `md/${mdFilename}`,
          inBuild("cornell-content.tex"),
          inBuild("cornell-cue.tex"),
          inBuild("cornell-summary.tex"),
        ])
      ))
    ) {
      return out;
    }
    if (!(await step(this.runScript("yaml_to_settings.py", ["settings/page.yaml", inBuild("cornell-page-settings.tex")])))) {
      return out;
    }

    let jobname;
    try {
      jobname = await this.topicSlug(yamlPath);
    } catch (err) {
      if (!(err instanceof PipelineError)) throw err;
      return { ...out, code: 1, stderr: `${out.stderr}${err.message}\n` };
    }

    // A copy of the template inside the build directory, so pdflatex gets
    // a short relative path -- the installed template's own path may hold
    // spaces or backslashes (e.g. under C:\Program Files) that TeX's
    // \input doesn't take kindly to.
    fs.copyFileSync(path.join(this.repoRoot, "settings", "template.tex"), path.join(buildDir, "cornell-template.tex"));
    // Same as the Makefile's -usepretex: \cnBuildDir tells the template
    // where the generated .tex fragments are.
    const latexArgs = [
      "-interaction=nonstopmode",
      "-halt-on-error",
      `-jobname=${jobname}`,
      "-output-directory=pdf",
      `\\def\\cnBuildDir{${texBuildDir}}\\input{${inBuild("cornell-template.tex")}}`,
    ];
    const logFile = path.join(this.pdfDir, `${jobname}.log`);
    for (let pass = 1; pass <= MAX_LATEX_PASSES; pass++) {
      if (!(await step(run("pdflatex", latexArgs, { cwd: this.projectRoot, env: this.childEnv() })))) return out;
      const log = isFile(logFile) ? fs.readFileSync(logFile, "latin1") : "";
      if (!RERUN_RE.test(log)) break;
    }
    for (const suffix of LATEX_AUX_SUFFIXES) fs.rmSync(path.join(this.pdfDir, jobname + suffix), { force: true });
    return out;
  }
}

// Derive a safe asset/folder name from `name`: drop any directory
// components (e.g. from "../../etc/passwd"), then collapse unsafe
// characters to "-" same as markdown filenames -- but keep the extension,
// since assets/folders (unlike notes) aren't all one fixed suffix.
function sanitizeName(name) {
  const safe = slugify(baseName(String(name)).trim());
  if (!safe) throw new PipelineError("Name can't be empty.");
  return safe;
}

// The user-facing "assets/..." path for `subdir`, for error messages.
const displayDir = (subdir) => (subdir ? `assets/${subdir}` : "assets");

// Run a command to completion, resolving (never rejecting on a non-zero
// exit) to its exit code and full output. A missing executable resolves
// with code 127 and the error in stderr, like a shell would report it.
function run(command, args, options) {
  return new Promise((resolve) => {
    // windowsHide: no console window flashing up per step on Windows.
    execFile(command, args, { ...options, windowsHide: true, maxBuffer: 64 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err && typeof err.code !== "number") {
        resolve({ code: 127, stdout: stdout || "", stderr: `${stderr || ""}${err.message}\n` });
        return;
      }
      resolve({ code: err ? err.code : 0, stdout, stderr });
    });
  });
}

module.exports = { Pipeline, PipelineError, HEADER_FIELDS, parseYaml };
