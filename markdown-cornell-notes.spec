# RPM packaging for Fedora and RHEL-family systems: the counterpart of the
# .deb (scripts/build_deb.sh). Build one locally with `make rpm`; Fedora
# COPR builds from this file too (see .copr/Makefile and
# docs/installation.md).
#
# Keep Version in step with app/package.json.
Name:           markdown-cornell-notes
Version:        2.0.0
Release:        1%{?dist}
Summary:        Cornell-style meeting notes generator (LaTeX/Markdown)

License:        MIT
URL:            https://github.com/forloop11/markdown-cornell-notes
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

# What `make build` runs: the scripts (Python, standard library only),
# pandoc, and pdflatex through latexmk...
Requires:       make
Requires:       python3
Requires:       pandoc
Requires:       latexmk
Requires:       /usr/bin/pdflatex
# ...and the LaTeX packages settings/template.tex loads, by file, so each
# pulls in just the TeX Live package that provides it.
Requires:       tex(amssymb.sty)
Requires:       tex(booktabs.sty)
Requires:       tex(fontenc.sty)
Requires:       tex(geometry.sty)
Requires:       tex(hyperref.sty)
Requires:       tex(longtable.sty)
Requires:       tex(tikz.sty)
Requires:       tex(xcolor.sty)
# The T1-encoded fonts fontenc's T1 option selects.
Requires:       texlive-ec
Requires:       texlive-cm-super

# The optional editor app is a PySide6 (Qt) desktop app; `make build`
# itself doesn't need it.
Recommends:     python3-pyside6

%description
Generates Cornell-note-taking-system PDFs from YAML header files and
Markdown content: each page has a header (topic, date, attendees, time), a
large notes panel with a cue column beside it, and a summary band below.

Run `markdown-cornell-notes init` in an empty directory to start a
project, and `markdown-cornell-notes build` to make its PDF. An optional
desktop editor (`markdown-cornell-notes app`, needing python3-pyside6)
shows notes beside their PDF.

%prep
%autosetup

%build
# Nothing to compile: scripts, a LaTeX template, and a Makefile.

%install
# Everything lands read-only under /usr/share, with a thin launcher on the
# PATH -- the same layout as the .deb.
install -d %{buildroot}%{_datadir}/%{name}
cp -a Makefile README.md requirements-dev.txt pytest.ini \
    scripts settings app tests md yaml assets docs \
    %{buildroot}%{_datadir}/%{name}/

install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/%{name} <<'LAUNCHER'
#!/bin/sh
# No -C: keep the caller's CWD as the project directory (see "make init")
# instead of running in place inside the root-owned /usr/share tree.
exec make -f /usr/share/markdown-cornell-notes/Makefile "$@"
LAUNCHER
chmod 755 %{buildroot}%{_bindir}/%{name}

%files
%license LICENSE
%doc README.md
%{_bindir}/%{name}
%{_datadir}/%{name}/

%changelog
* Sat Oct 10 2026 Todd C. Takala <todd.c.takala@gmail.com> - 2.0.0-1
- First RPM package. The editor app is now built on Qt (PySide6).
