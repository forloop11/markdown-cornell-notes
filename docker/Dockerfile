# Minimal toolchain for building the Cornell notes PDF: pdflatex + latexmk,
# only the LaTeX packages this template actually uses (no texlive-full),
# pandoc for Markdown, and Python 3 (stdlib only) for the generator
# scripts. Mount the project directory and run `make build`.
#
# cm-super (~50MB) is included so bold/italic Computer Modern text at odd
# sizes uses proper vector fonts. Without it, pdflatex still builds, but
# falls back to generating bitmap fonts on the fly via METAFONT (slower,
# needs a writable font-cache dir, blurs when the PDF is zoomed) -- drop
# it below if the smaller image is worth that trade-off.
FROM debian:bookworm-slim

RUN apt-get update && apt-get install --no-install-recommends -y \
      make \
      python3 \
      pandoc \
      latexmk \
      texlive-latex-base \
      texlive-latex-recommended \
      texlive-pictures \
      cm-super \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENTRYPOINT ["make"]
CMD ["build"]
