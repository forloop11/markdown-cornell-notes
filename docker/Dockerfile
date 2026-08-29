# Toolchain for building the Cornell notes PDF: pdflatex + latexmk, only the
# LaTeX packages this template actually uses (no texlive-full), pandoc for
# Markdown, Python 3 (stdlib only) for the generator scripts, and Streamlit
# for the `app`/`docker-app` editor UI. Mount the project directory and run
# `make app` (default, see docker-app below) or `make build`.
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
      python3-pip \
      pandoc \
      latexmk \
      texlive-latex-base \
      texlive-latex-recommended \
      texlive-pictures \
      cm-super \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# --break-system-packages: Debian's system Python refuses plain `pip
# install` (PEP 668, "externally managed environment"); safe here since the
# whole container is dedicated to this one app, so there's no environment
# to conflict with. requirements.txt is copied in (rather than relying on
# the bind mount) so this layer is cached independently of source changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

EXPOSE 8501

ENTRYPOINT ["make"]
CMD ["app"]
