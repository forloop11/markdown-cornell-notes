TEX      := cornell-notes.tex
PDF      := $(TEX:.tex=.pdf)
YAML     := meeting.yaml
BUILDDIR := build
HEADER   := $(BUILDDIR)/cornell-header.tex
MD       := notes.md
CONTENT  := $(BUILDDIR)/cornell-content.tex
LATEXMK  := latexmk
LATEXOPTS := -pdf -interaction=nonstopmode -halt-on-error

.PHONY: build clean distclean

build: $(PDF)
	$(LATEXMK) -c $(TEX)

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
