TEX      := settings/template.tex
YAML     := yaml/header.yaml
JOBNAME  := $(shell python3 scripts/topic_slug.py $(YAML))
OUTDIR   := pdf
PDF      := $(OUTDIR)/$(JOBNAME).pdf
BUILDDIR := build
HEADER   := $(BUILDDIR)/cornell-header.tex
MD       := md/notes.md
CONTENT  := $(BUILDDIR)/cornell-content.tex
CUE      := $(BUILDDIR)/cornell-cue.tex
SUMMARY  := $(BUILDDIR)/cornell-summary.tex
SETTINGS_YAML := settings/page.yaml
SETTINGS := $(BUILDDIR)/cornell-page-settings.tex
LATEXMK  := latexmk
LATEXOPTS := -pdf -interaction=nonstopmode -halt-on-error -jobname=$(JOBNAME) -outdir=$(OUTDIR)
DOCKER_IMAGE := cornell-notes

EXAMPLE_MD       := md/notes-example.md
EXAMPLE_YAML     := yaml/header-example.yaml
EXAMPLE_BUILDDIR := build/example

.PHONY: build clean distclean docker build-example app docker-app

build: $(PDF)
	$(LATEXMK) -c -jobname=$(JOBNAME) -outdir=$(OUTDIR) $(TEX)

# Builds pdf/<slug>.pdf from md/notes-example.md / yaml/header-example.yaml instead of
# md/notes.md / yaml/header.yaml, using its own build/example/ scratch dir so it
# never collides with (or goes stale against) the regular build's
# intermediate files.
build-example:
	$(MAKE) build MD=$(EXAMPLE_MD) YAML=$(EXAMPLE_YAML) BUILDDIR=$(EXAMPLE_BUILDDIR)

# Same as `build`, but run inside the Docker image (see docker/Dockerfile)
# instead of requiring pdflatex/latexmk/pandoc to be installed locally. Runs
# as the calling user so the output isn't left root-owned on the host.
docker:
	docker build -t $(DOCKER_IMAGE) -f docker/Dockerfile .
	docker run --rm -v "$(CURDIR)":/workspace -u "$$(id -u):$$(id -g)" $(DOCKER_IMAGE)

# Runs the Streamlit editor app (requires `pip install -r requirements.txt`
# first; see README.md). Binds 0.0.0.0 rather than Streamlit's usual
# localhost-only default so this also works unchanged as the `docker-app`
# target below, where the container's published port has to be reachable
# from outside it.
app:
	streamlit run app/streamlit_app.py --server.address=0.0.0.0

# Same as `app`, but run inside the Docker image, with the app's port
# published to the host. Overrides the image's default `make build`
# command (see docker/Dockerfile's ENTRYPOINT/CMD) with `make app` instead.
docker-app:
	docker build -t $(DOCKER_IMAGE) -f docker/Dockerfile .
	docker run --rm -p 8501:8501 -v "$(CURDIR)":/workspace -u "$$(id -u):$$(id -g)" $(DOCKER_IMAGE) app

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
