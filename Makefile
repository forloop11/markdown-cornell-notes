# Directory containing this Makefile itself, not the caller's CWD -- lets
# the installed package (Makefile living under /usr/share/markdown-cornell-notes,
# invoked via `make -f` from wherever the user's project lives) find its own
# scripts/settings/app regardless of where `make` is run from. MD/YAML/
# SETTINGS_YAML stay CWD-relative on purpose: those are the user's project
# files, initialized into the CWD by `make init`.
MCN_ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

TEX      := $(MCN_ROOT)settings/template.tex
MD       := md/notes.md
# The header yaml is paired with MD by filename: md/<stem>.md <-> yaml/<stem>.yaml.
# Override YAML directly if a given MD needs a differently-named pair.
YAML     := yaml/$(basename $(notdir $(MD))).yaml
# $(YAML) doesn't exist yet on a freshly-`init`ed project (or before the
# user has created one at all) -- guard with $(wildcard) so parsing the
# Makefile for `make init`/`make deb` doesn't shell out to a script that's
# guaranteed to fail on a missing file. topic_slug.py's own "cornell-notes"
# fallback (for a YAML with no topic/date/location) is mirrored here for
# a YAML that isn't there at all.
JOBNAME  := $(if $(wildcard $(YAML)),$(shell python3 $(MCN_ROOT)scripts/topic_slug.py $(YAML)),cornell-notes)
OUTDIR   := pdf
PDF      := $(OUTDIR)/$(JOBNAME).pdf
BUILDDIR := build
HEADER   := $(BUILDDIR)/cornell-header.tex
CONTENT  := $(BUILDDIR)/cornell-content.tex
CUE      := $(BUILDDIR)/cornell-cue.tex
SUMMARY  := $(BUILDDIR)/cornell-summary.tex
SETTINGS_YAML := settings/page.yaml
SETTINGS := $(BUILDDIR)/cornell-page-settings.tex
LATEXMK  := latexmk

# Targets below don't need a scaffolded project in the CWD; everything else
# (build, build-example, the default goal, ...) does. Without this check, a
# missing $(MD)/$(YAML)/$(SETTINGS_YAML) surfaces as Make's cryptic "No rule
# to make target 'yaml/notes.yaml'" instead of pointing at the actual fix.
# build-example is skipped for the MD/YAML half: it re-invokes $(MAKE) with
# MD/YAML overridden to the bundled example files (checked again, correctly,
# in that recursive call) -- checking the *default* $(MD)/$(YAML) here would
# wrongly demand a project the example build never touches. It still needs
# $(SETTINGS_YAML) though, since that one isn't overridden.
NO_PROJECT_NEEDED := init deb windows macos appimage install-appimage uninstall-appimage clean distclean app test
NEEDS_PROJECT := $(filter-out $(NO_PROJECT_NEEDED),$(or $(MAKECMDGOALS),build))
NEEDS_MD_YAML := $(filter-out build-example,$(NEEDS_PROJECT))
ifneq ($(NEEDS_MD_YAML),)
ifeq ($(wildcard $(MD)),)
$(error $(MD) not found -- run 'markdown-cornell-notes init' (or 'make init' from a checkout) first to scaffold a new project here, or pass MD=/YAML= to point at an existing one)
endif
ifeq ($(wildcard $(YAML)),)
$(error $(YAML) not found -- run 'markdown-cornell-notes init' (or 'make init' from a checkout) first to scaffold a new project here, or pass MD=/YAML= to point at an existing one)
endif
endif
ifneq ($(NEEDS_PROJECT),)
ifeq ($(wildcard $(SETTINGS_YAML)),)
$(error $(SETTINGS_YAML) not found -- run 'markdown-cornell-notes init' (or 'make init' from a checkout) first to scaffold a new project here)
endif
endif
# -usepretex defines \cnBuildDir (read by settings/template.tex's \input
# calls) before the document loads, so a BUILDDIR override on the command
# line actually reaches the .tex fragments latexmk compiles -- without
# this, template.tex's \input paths are effectively hardcoded to plain
# build/, so build-example/the editor app's isolated BUILDDIR would
# generate fragments latexmk never actually reads, silently recompiling
# whatever's left in build/ from the last plain `make build` instead.
LATEXOPTS := -pdf -interaction=nonstopmode -halt-on-error -jobname=$(JOBNAME) -outdir=$(OUTDIR) -usepretex='\def\cnBuildDir{$(BUILDDIR)}'

# Bundled demo files, not the user's project -- resolved against MCN_ROOT
# (not CWD) so `build-example` works from any project directory once
# installed, the same as scripts/settings/app above.
EXAMPLE_MD       := $(MCN_ROOT)md/notes-example.md
EXAMPLE_YAML     := $(MCN_ROOT)yaml/notes-example.yaml
EXAMPLE_BUILDDIR := build/example

.PHONY: build clean distclean build-example app deb windows macos appimage install-appimage uninstall-appimage init test

build: $(PDF)
	$(LATEXMK) -c -jobname=$(JOBNAME) -outdir=$(OUTDIR) $(TEX)

# Builds pdf/<slug>.pdf from md/notes-example.md / yaml/notes-example.yaml instead of
# md/notes.md / yaml/notes.yaml, using its own build/example/ scratch dir so it
# never collides with (or goes stale against) the regular build's
# intermediate files.
#
# -f $(lastword $(MAKEFILE_LIST)) (the same expression MCN_ROOT is derived
# from above) re-passes whichever Makefile this recursive call's parent was
# invoked with. Without it, the installed wrapper's `-f
# /usr/share/markdown-cornell-notes/Makefile` doesn't carry over to this
# child `$(MAKE)` -- it falls back to make's default of looking for a
# Makefile in the caller's CWD (the user's project directory), which
# doesn't have one, failing with "No rule to make target 'build'." A git
# checkout's bare `make build-example` (no -f, implicit ./Makefile) isn't
# affected either way, since $(lastword $(MAKEFILE_LIST)) there just
# resolves to that same implicit Makefile.
build-example:
	$(MAKE) -f $(lastword $(MAKEFILE_LIST)) build MD=$(EXAMPLE_MD) YAML=$(EXAMPLE_YAML) BUILDDIR=$(EXAMPLE_BUILDDIR)

# Opens the editor app on the project in the CWD (see docs/editor-app.md).
# It's a Python (PySide6/Qt) desktop app, so it needs PySide6 with Qt
# WebEngine on top of the build's own requirements: from a checkout,
#
#     python3 -m venv app/.venv && app/.venv/bin/pip install -r app/requirements.txt
#
# sets that up where this target looks first. Otherwise it runs with
# python3 -- for a system-wide PySide6, e.g. the distribution's packages an
# installed .deb recommends -- or whichever interpreter APP_PYTHON names.
#
# APP_FLAGS passes extra Qt/Chromium switches, e.g. `make app
# APP_FLAGS=--no-sandbox` where the OS blocks Chromium's sandbox (see
# docs/editor-app.md).
APP_PYTHON ?= $(if $(wildcard $(MCN_ROOT)app/.venv/bin/python),$(MCN_ROOT)app/.venv/bin/python,python3)
APP_FLAGS  ?=
app:
	@exec "$(APP_PYTHON)" "$(MCN_ROOT)app/main.py" $(APP_FLAGS)

# Unit tests, via pytest (requires `pip install -r requirements-dev.txt`
# first): the build scripts' Python helpers and the editor app's backend
# (app/pipeline.py, app/api.py, app/header_form.py), plus the app's window
# itself where PySide6 is installed (tests/test_window.py skips itself
# otherwise, so run with APP_PYTHON's interpreter to include it). Everything
# runs against temp-dir projects (see tests/conftest.py), never the CWD's
# own md/yaml/assets, so no scaffolded project is needed (or touched).
# Rendering is only covered where pandoc and pdflatex are installed.
test:
	cd $(MCN_ROOT) && "$(APP_PYTHON)" -m pytest

# Packages this project as a .deb (dist/markdown-cornell-notes_<version>.deb)
# for Debian/Ubuntu -- see scripts/build_deb.sh for what it stages and which
# system packages it declares as Depends.
deb:
	$(MCN_ROOT)scripts/build_deb.sh

# Builds the Windows installer for the editor app
# (dist/windows/Markdown-Cornell-Notes-Setup-<version>.exe), with Python,
# Qt (PySide6), pandoc, and a minimal TeX Live bundled in -- see
# scripts/build_windows.sh. Needs an x86_64 Linux host, with NSIS's
# makensis or else podman or docker to run it in.
windows:
	$(MCN_ROOT)scripts/build_windows.sh

# Builds the editor app for Apple Silicon Macs
# (dist/macos/Markdown-Cornell-Notes-<version>-arm64-mac.zip), bundled the
# same way and ad-hoc signed -- see scripts/build_macos.sh. Needs an
# x86_64 Linux host; no Mac.
macos:
	$(MCN_ROOT)scripts/build_macos.sh

# Builds the editor app for x86_64 Linux as a single-file AppImage
# (dist/linux/Markdown-Cornell-Notes-<version>-x86_64.AppImage), bundled
# the same way -- see scripts/build_appimage.sh. Needs an x86_64 Linux host.
appimage:
	$(MCN_ROOT)scripts/build_appimage.sh

# Installs that AppImage for the current user -- into ~/Applications (or
# APPIMAGE_DIR), with an application-menu entry and icon -- and removes it
# again; see scripts/install_appimage.sh. Run `make appimage` first.
install-appimage:
	$(MCN_ROOT)scripts/install_appimage.sh install

uninstall-appimage:
	$(MCN_ROOT)scripts/install_appimage.sh uninstall

# Scaffolds a fresh project (md/, yaml/, settings/page.yaml, pdf/, assets/)
# in the CWD from the bundled defaults, so the installed package -- whose
# Makefile lives read-only under /usr/share -- has somewhere writable to
# point MD/YAML/SETTINGS_YAML at. assets/tux.jpg is included because
# notes-example.md embeds it, as a demo of the Markdown image syntax.
# Refuses to clobber an existing project, and is a no-op when run from
# within the package's own source tree (MCN_ROOT == CWD, e.g. during
# development).
init:
	@if [ "$(abspath .)/" = "$(MCN_ROOT)" ]; then \
		echo "Already in the markdown-cornell-notes source tree; nothing to init." >&2; \
		exit 1; \
	fi
	@for d in md yaml settings pdf assets; do \
		if [ -e "$$d" ]; then \
			echo "Refusing to init: '$$d' already exists in $$(pwd)" >&2; \
			exit 1; \
		fi; \
	done
	mkdir -p md yaml settings pdf assets
	cp $(MCN_ROOT)md/notes-example.md md/notes.md
	cp $(MCN_ROOT)yaml/notes-example.yaml yaml/notes.yaml
	cp $(MCN_ROOT)settings/page.yaml settings/page.yaml
	cp $(MCN_ROOT)assets/tux.jpg assets/tux.jpg
	@echo "Initialized a new markdown-cornell-notes project in $$(pwd)"
	@echo "Edit yaml/notes.yaml, md/notes.md, and settings/page.yaml, then run: markdown-cornell-notes build"

$(HEADER): $(YAML) $(MCN_ROOT)scripts/yaml_to_header.py $(MCN_ROOT)scripts/simple_yaml.py
	python3 $(MCN_ROOT)scripts/yaml_to_header.py $(YAML) $(HEADER)

$(CONTENT) $(CUE) $(SUMMARY) &: $(MD) $(MCN_ROOT)scripts/markdown_to_pages.py
	python3 $(MCN_ROOT)scripts/markdown_to_pages.py $(MD) $(CONTENT) $(CUE) $(SUMMARY)

$(SETTINGS): $(SETTINGS_YAML) $(MCN_ROOT)scripts/yaml_to_settings.py $(MCN_ROOT)scripts/simple_yaml.py
	python3 $(MCN_ROOT)scripts/yaml_to_settings.py $(SETTINGS_YAML) $(SETTINGS)

$(PDF): $(TEX) $(HEADER) $(CONTENT) $(CUE) $(SUMMARY) $(SETTINGS) | $(OUTDIR)
	$(LATEXMK) $(LATEXOPTS) $(TEX)

$(OUTDIR):
	mkdir -p $@

clean:
	$(LATEXMK) -c -jobname=$(JOBNAME) -outdir=$(OUTDIR) $(TEX)

distclean:
	$(LATEXMK) -C -jobname=$(JOBNAME) -outdir=$(OUTDIR) $(TEX)
	rm -f $(HEADER) $(CONTENT) $(CUE) $(SUMMARY) $(SETTINGS)
