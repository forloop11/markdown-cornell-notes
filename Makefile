TEX      := settings/template.tex
JOBNAME  := cornell-notes
PDF      := $(JOBNAME).pdf
YAML     := header.yaml
BUILDDIR := build
HEADER   := $(BUILDDIR)/cornell-header.tex
MD       := notes.md
CONTENT  := $(BUILDDIR)/cornell-content.tex
SETTINGS_YAML := settings/page.yaml
SETTINGS := $(BUILDDIR)/cornell-page-settings.tex
LATEXMK  := latexmk
LATEXOPTS := -pdf -interaction=nonstopmode -halt-on-error -jobname=$(JOBNAME)
DOCKER_IMAGE := cornell-notes

.PHONY: build clean distclean docker

build: $(PDF)
	$(LATEXMK) -c -jobname=$(JOBNAME) $(TEX)

# Same as `build`, but run inside the Docker image (see docker/Dockerfile)
# instead of requiring pdflatex/latexmk/pandoc to be installed locally. Runs
# as the calling user so the output isn't left root-owned on the host.
docker:
	docker build -t $(DOCKER_IMAGE) -f docker/Dockerfile .
	docker run --rm -v "$(CURDIR)":/workspace -u "$$(id -u):$$(id -g)" $(DOCKER_IMAGE)

$(HEADER): $(YAML) scripts/yaml_to_header.py scripts/simple_yaml.py
	python3 scripts/yaml_to_header.py $(YAML) $(HEADER)

$(CONTENT): $(MD) scripts/markdown_to_pages.py
	python3 scripts/markdown_to_pages.py $(MD) $(CONTENT)

$(SETTINGS): $(SETTINGS_YAML) scripts/yaml_to_settings.py scripts/simple_yaml.py
	python3 scripts/yaml_to_settings.py $(SETTINGS_YAML) $(SETTINGS)

$(PDF): $(TEX) $(HEADER) $(CONTENT) $(SETTINGS)
	$(LATEXMK) $(LATEXOPTS) $(TEX)

clean:
	$(LATEXMK) -c -jobname=$(JOBNAME) $(TEX)

distclean:
	$(LATEXMK) -C -jobname=$(JOBNAME) $(TEX)
	rm -f $(HEADER) $(CONTENT) $(SETTINGS)
