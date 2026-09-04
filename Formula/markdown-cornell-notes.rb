class MarkdownCornellNotes < Formula
  desc "Cornell-style meeting notes generator (LaTeX/Markdown)"
  homepage "https://github.com/forloop11/markdown-cornell-notes"
  license "MIT"

  # No tagged release includes the CWD-relative build fixes yet (see
  # CHANGELOG/README "Installing as a system package") -- update url/sha256
  # once a new tag is cut, e.g.:
  #   url "https://github.com/forloop11/markdown-cornell-notes/archive/refs/tags/vX.Y.Z.tar.gz"
  #   sha256 "..." # `curl -L <url> | shasum -a 256`
  # Until then, install with --HEAD (see README).
  head "https://github.com/forloop11/markdown-cornell-notes.git", branch: "main"

  depends_on "pandoc"
  depends_on "python@3.13"

  # No `depends_on` for LaTeX itself -- MacTeX/BasicTeX ship as Homebrew
  # casks, not formulas, and MacTeX alone is several GB. See caveats below.

  def install
    # Mirrors scripts/build_deb.sh's Debian packaging: stage everything
    # under a private prefix (there, /usr/share/markdown-cornell-notes;
    # here, libexec) and drop a thin `make -f` wrapper on the PATH. No
    # rsync --exclude list needed here (unlike build_deb.sh) since the
    # GitHub tarball/HEAD checkout only ever contains git-tracked files --
    # /build/, /dist/, __pycache__/, and node_modules/ are all gitignored
    # and never make it into the archive in the first place.
    libexec.install Dir["*"]

    (bin/"markdown-cornell-notes").write <<~SH
      #!/bin/sh
      # No -C: keep the caller's CWD as the project directory (`markdown-cornell-notes init`)
      # instead of running in place inside the read-only Cellar.
      exec make -f "#{libexec}/Makefile" "$@"
    SH
  end

  def caveats
    <<~EOS
      markdown-cornell-notes needs a LaTeX install (latexmk, plus the tikz,
      xcolor, geometry, hyperref, amssymb, longtable, and booktabs packages).
      The lightest way to get one on macOS is BasicTeX:

        brew install --cask basictex
        eval "$(/usr/libexec/path_helper)"
        sudo tlmgr update --self
        sudo tlmgr install latexmk tikz xcolor geometry hyperref amsmath longtable booktabs

      (MacTeX -- `brew install --cask mactex-no-gui` -- includes all of
      these already, at the cost of a multi-GB download.)

      To start a new project:

        mkdir ~/notes && cd ~/notes
        markdown-cornell-notes init
        markdown-cornell-notes build

      The optional Streamlit editor app needs one extra pip install:

        pip install -r #{libexec}/requirements.txt
        cd ~/notes && markdown-cornell-notes app
    EOS
  end

  test do
    # Exercises `make init` (pure file staging, no LaTeX/pandoc needed) to
    # confirm the installed Makefile/wrapper resolve their own scripts via
    # libexec correctly and scaffold a project in the CWD rather than
    # inside the Cellar.
    system bin/"markdown-cornell-notes", "init"
    assert_path_exists testpath/"yaml/notes.yaml"
    assert_path_exists testpath/"md/notes.md"
    assert_path_exists testpath/"settings/page.yaml"
  end
end
