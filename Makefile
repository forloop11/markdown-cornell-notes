TEX      := settings/template.tex
YAML     := header.yaml
JOBNAME  := $(shell python3 scripts/topic_slug.py $(YAML))
OUTDIR   := notes
PDF      := $(OUTDIR)/$(JOBNAME).pdf
BUILDDIR := build
HEADER   := $(BUILDDIR)/cornell-header.tex
MD       := notes.md
CONTENT  := $(BUILDDIR)/cornell-content.tex
CUE      := $(BUILDDIR)/cornell-cue.tex
SUMMARY  := $(BUILDDIR)/cornell-summary.tex
SETTINGS_YAML := settings/page.yaml
SETTINGS := $(BUILDDIR)/cornell-page-settings.tex
LATEXMK  := latexmk
LATEXOPTS := -pdf -interaction=nonstopmode -halt-on-error -jobname=$(JOBNAME) -outdir=$(OUTDIR)
DOCKER_IMAGE := cornell-notes

.PHONY: build clean distclean docker

build: $(PDF)
	$(LATEXMK) -c -jobname=$(JOBNAME) -outdir=$(OUTDIR) $(TEX)

# Same as `build`, but run inside the Docker image (see docker/Dockerfile)
# instead of requiring pdflatex/latexmk/pandoc to be installed locally. Runs
# as the calling user so the output isn't left root-owned on the host.
docker:
	docker build -t $(DOCKER_IMAGE) -f docker/Dockerfile .
	docker run --rm -v "$(CURDIR)":/workspace -u "$$(id -u):$$(id -g)" $(DOCKER_IMAGE)

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
