TEX      := cornell-notes.tex
PDF      := $(TEX:.tex=.pdf)
YAML     := meeting.yaml
BUILDDIR := build
HEADER   := $(BUILDDIR)/cornell-header.tex
MD       := notes.md
CONTENT  := $(BUILDDIR)/cornell-content.tex
LATEXMK  := latexmk
LATEXOPTS := -pdf -interaction=nonstopmode -halt-on-error
DOCKER_IMAGE := cornell-notes

.PHONY: build clean distclean docker

build: $(PDF)
	$(LATEXMK) -c $(TEX)

# Same as `build`, but run inside the Docker image (see Dockerfile) instead
# of requiring pdflatex/latexmk/pandoc to be installed locally. Runs as the
# calling user so the output isn't left root-owned on the host.
docker:
	docker build -t $(DOCKER_IMAGE) .
	docker run --rm -v "$(CURDIR)":/workspace -u "$$(id -u):$$(id -g)" $(DOCKER_IMAGE)

$(HEADER): $(YAML) scripts/yaml_to_header.py
	python3 scripts/yaml_to_header.py $(YAML) $(HEADER)

$(CONTENT): $(MD) scripts/markdown_to_pages.py
	python3 scripts/markdown_to_pages.py $(MD) $(CONTENT)

$(PDF): $(TEX) $(HEADER) $(CONTENT)
	$(LATEXMK) $(LATEXOPTS) $(TEX)

clean:
	$(LATEXMK) -c $(TEX)

distclean:
	$(LATEXMK) -C $(TEX)
	rm -f $(HEADER) $(CONTENT)
