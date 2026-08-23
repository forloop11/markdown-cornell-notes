TEX      := cornell-notes.tex
PDF      := $(TEX:.tex=.pdf)
LATEXMK  := latexmk
LATEXOPTS := -pdf -interaction=nonstopmode -halt-on-error

.PHONY: build clean distclean

build: $(PDF)

$(PDF): $(TEX)
	$(LATEXMK) $(LATEXOPTS) $<

clean:
	$(LATEXMK) -c $(TEX)

distclean:
	$(LATEXMK) -C $(TEX)
