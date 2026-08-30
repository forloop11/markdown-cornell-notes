TEX      := settings/template.tex
MD       := md/notes.md
# The header yaml is paired with MD by filename: md/<stem>.md <-> yaml/<stem>.yaml.
# Override YAML directly if a given MD needs a differently-named pair.
YAML     := yaml/$(basename $(notdir $(MD))).yaml
JOBNAME  := $(shell python3 scripts/topic_slug.py $(YAML))
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
# -usepretex defines \cnBuildDir (read by settings/template.tex's \input
# calls) before the document loads, so a BUILDDIR override on the command
# line actually reaches the .tex fragments latexmk compiles -- without
# this, template.tex's \input paths are effectively hardcoded to plain
# build/, so build-example/the Streamlit app's isolated BUILDDIR would
# generate fragments latexmk never actually reads, silently recompiling
# whatever's left in build/ from the last plain `make build` instead.
LATEXOPTS := -pdf -interaction=nonstopmode -halt-on-error -jobname=$(JOBNAME) -outdir=$(OUTDIR) -usepretex='\def\cnBuildDir{$(BUILDDIR)}'

EXAMPLE_MD       := md/notes-example.md
EXAMPLE_YAML     := yaml/notes-example.yaml
EXAMPLE_BUILDDIR := build/example

.PHONY: build clean distclean build-example app

build: $(PDF)
	$(LATEXMK) -c -jobname=$(JOBNAME) -outdir=$(OUTDIR) $(TEX)

# Builds pdf/<slug>.pdf from md/notes-example.md / yaml/notes-example.yaml instead of
# md/notes.md / yaml/notes.yaml, using its own build/example/ scratch dir so it
# never collides with (or goes stale against) the regular build's
# intermediate files.
build-example:
	$(MAKE) build MD=$(EXAMPLE_MD) YAML=$(EXAMPLE_YAML) BUILDDIR=$(EXAMPLE_BUILDDIR)

# Runs the Streamlit editor app (requires `pip install -r requirements.txt`
# first; see README.md). Binds 0.0.0.0 rather than Streamlit's usual
# localhost-only default so it's reachable from other machines on the
# network, not just localhost.
app:
	streamlit run app/streamlit_app.py --server.address=0.0.0.0

$(HEADER): $(YAML) scripts/yaml_to_header.py scripts/simple_yaml.py
	python3 scripts/yaml_to_header.py $(YAML) $(HEADER)

$(CONTENT) $(CUE) $(SUMMARY) &: $(MD) scripts/markdown_to_pages.py
	python3 scripts/markdown_to_pages.py $(MD) $(CONTENT) $(CUE) $(SUMMARY)

$(SETTINGS): $(SETTINGS_YAML) scripts/yaml_to_settings.py scripts/simple_yaml.py
	python3 scripts/yaml_to_settings.py $(SETTINGS_YAML) $(SETTINGS)

$(PDF): $(TEX) $(HEADER) $(CONTENT) $(CUE) $(SUMMARY) $(SETTINGS) | $(OUTDIR)
	$(LATEXMK) $(LATEXOPTS) $(TEX)

$(OUTDIR):
	mkdir -p $@

clean:
	$(LATEXMK) -c -jobname=$(JOBNAME) -outdir=$(OUTDIR) $(TEX)

distclean:
	$(LATEXMK) -C -jobname=$(JOBNAME) -outdir=$(OUTDIR) $(TEX)
	rm -f $(HEADER) $(CONTENT) $(CUE) $(SUMMARY) $(SETTINGS)
