#!/usr/bin/env bash
# Packages this project as an RPM (dist/rpm/markdown-cornell-notes-<version>-
# <release>.noarch.rpm) for Fedora and RHEL-family systems, from
# markdown-cornell-notes.spec: like the .deb, the pipeline and app under
# /usr/share, a launcher in /usr/bin, and the system's own TeX Live,
# pandoc, and Python as dependencies.
#
# Uses rpmbuild from the host if it's installed (`sudo dnf install
# rpm-build`), else runs it in a Fedora container (podman or docker).
#
# The package holds the working tree's files as they are now -- every
# file git tracks or would track, committed or not.
#
# Usage: scripts/build_rpm.sh   (or `make rpm`)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPEC="$ROOT/markdown-cornell-notes.spec"
NAME="markdown-cornell-notes"
VERSION="$(sed -n 's/^Version: *//p' "$SPEC")"
OUT="$ROOT/dist/rpm"
TOP="$OUT/rpmbuild"
RPM_IMAGE="registry.fedoraproject.org/fedora:latest" # only used without an rpmbuild on the host

app_version="$(sed -n 's/^  "version": "\(.*\)",$/\1/p' "$ROOT/app/package.json")"
if [ "$VERSION" != "$app_version" ]; then
  echo "The spec says version $VERSION but app/package.json says $app_version; make them agree." >&2
  exit 1
fi

rm -rf "$OUT"
mkdir -p "$TOP"/{SOURCES,SPECS}
cp "$SPEC" "$TOP/SPECS/"
# The source tarball: tracked files, plus new ones not yet added (but
# nothing .gitignore excludes).
(cd "$ROOT" && git ls-files -z --cached --others --exclude-standard |
  while IFS= read -r -d '' file; do [ -e "$file" ] && printf '%s\0' "$file"; done |
  tar --null -T - --transform "s,^,$NAME-$VERSION/," -czf "$TOP/SOURCES/$NAME-$VERSION.tar.gz")

if command -v rpmbuild > /dev/null; then
  rpmbuild --define "_topdir $TOP" -ba "$TOP/SPECS/$NAME.spec"
else
  container="${CONTAINER:-$(command -v podman || command -v docker || true)}"
  if [ -z "$container" ]; then
    echo "Needs rpmbuild (sudo dnf install rpm-build), or podman or docker to run it in $RPM_IMAGE." >&2
    exit 1
  fi
  # label=disable: on SELinux hosts (e.g. Fedora), lets the container read
  # the bind mount without relabeling the checkout.
  "$container" run --rm --security-opt label=disable -v "$TOP":/rpmbuild "$RPM_IMAGE" \
    sh -c 'dnf -y -q install rpm-build > /dev/null && rpmbuild --define "_topdir /rpmbuild" -ba /rpmbuild/SPECS/'"$NAME"'.spec'
fi

cp "$TOP"/RPMS/noarch/*.rpm "$TOP"/SRPMS/*.src.rpm "$OUT/"
ls -lh "$OUT"/*.rpm
