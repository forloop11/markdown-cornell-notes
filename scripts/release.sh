#!/usr/bin/env bash
# The steps of a release, so each one is done the same way every time:
#
#   scripts/release.sh bump 2.2.0     set the version everywhere it's written
#   (write docs/release-notes/2.2.0.md, commit, push)
#   scripts/release.sh build          test, then build the packages into
#                                     dist/release/<version>/ with SHA256SUMS
#   scripts/release.sh publish        create the GitHub release v<version> at
#                                     the current commit, with those files
#
# The version lives in app/package.json; `bump` copies it to
# app/package-lock.json and the RPM spec (with a %changelog entry), which
# is everywhere else it's written down.
#
# `build` makes the packages that can be checked on a Linux host -- the
# AppImage, the .deb, and the RPM -- unless told otherwise:
#
#   scripts/release.sh build appimage deb rpm windows macos
#
# Checksums go in a SHA256SUMS file published with the packages, rather
# than into the release notes, so the notes can be written (and committed)
# before the packages exist.
#
# `publish` refuses to run unless the working tree is clean, the current
# commit is on GitHub, and the notes file exists: the tag it creates then
# marks exactly the code the packages were built from. It asks before
# publishing (--yes to skip the question).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

version() { sed -n 's/^  "version": "\(.*\)",$/\1/p' app/package.json; }

die() {
  echo "release.sh: $*" >&2
  exit 1
}

bump() {
  local new="${1:-}"
  [[ "$new" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "usage: release.sh bump <major.minor.patch>"
  local old
  old="$(version)"
  [ "$new" != "$old" ] || die "the version is already $new"
  sed -i "s/^  \"version\": \"$old\",\$/  \"version\": \"$new\",/" app/package.json
  # package-lock.json names the version twice near its top: the package's
  # own, and the root entry's under "packages".
  sed -i "1,12s/^\(\s*\)\"version\": \"$old\",\$/\1\"version\": \"$new\",/" app/package-lock.json
  sed -i "s/^Version:\(\s*\)$old\$/Version:\1$new/" markdown-cornell-notes.spec
  local entry
  entry="* $(LC_ALL=C date '+%a %b %d %Y') Todd C. Takala <todd.c.takala@gmail.com> - $new-1"
  # (The entry points at the release notes rather than repeating them.)
  sed -i "s|^%changelog\$|%changelog\n$entry\n- Version $new; see docs/release-notes/$new.md.\n|" markdown-cornell-notes.spec
  [ "$(version)" = "$new" ] || die "couldn't set the version in app/package.json"
  grep -q "^Version: *$new\$" markdown-cornell-notes.spec || die "couldn't set the version in the RPM spec"
  echo "Version $old -> $new (app/package.json, app/package-lock.json, markdown-cornell-notes.spec)."
  echo "Next: write docs/release-notes/$new.md, commit, push, then: scripts/release.sh build"
}

build() {
  local targets=("$@")
  [ ${#targets[@]} -gt 0 ] || targets=(appimage deb rpm)
  local v out
  v="$(version)"
  out="dist/release/$v"

  echo "== Testing"
  make test

  rm -rf "$out"
  mkdir -p "$out"
  local target
  for target in "${targets[@]}"; do
    echo "== Building: $target"
    case "$target" in
      appimage)
        make appimage
        cp "dist/linux/Markdown-Cornell-Notes-$v-x86_64.AppImage" "dist/linux/Markdown-Cornell-Notes-$v-x86_64.AppImage.zsync" "$out/"
        ;;
      deb)
        scripts/build_deb.sh "$v" > /dev/null
        cp "dist/markdown-cornell-notes_$v.deb" "$out/"
        ;;
      rpm)
        make rpm
        cp dist/rpm/markdown-cornell-notes-"$v"-*.noarch.rpm dist/rpm/markdown-cornell-notes-"$v"-*.src.rpm "$out/"
        ;;
      windows)
        make windows
        cp "dist/windows/Markdown-Cornell-Notes-Setup-$v.exe" "$out/"
        ;;
      macos)
        make macos
        cp "dist/macos/Markdown-Cornell-Notes-$v-arm64-mac.zip" "$out/"
        ;;
      *) die "unknown package '$target' (appimage, deb, rpm, windows, macos)" ;;
    esac
  done

  # The .zsync is derived from the AppImage and checked by the tools that
  # use it; everything else gets a checksum.
  (cd "$out" && sha256sum -- $(ls | grep -v -e '\.zsync$' -e '^SHA256SUMS$') > SHA256SUMS)
  echo "== Built in $out:"
  ls -lh "$out"
  echo "Next: scripts/release.sh publish"
}

publish() {
  local yes=""
  [ "${1:-}" = "--yes" ] && yes=1
  local v out notes sha
  v="$(version)"
  out="dist/release/$v"
  notes="docs/release-notes/$v.md"
  sha="$(git rev-parse HEAD)"

  command -v gh > /dev/null || die "needs the GitHub CLI (gh)"
  [ -f "$out/SHA256SUMS" ] || die "nothing built for $v -- run: scripts/release.sh build"
  [ -f "$notes" ] || die "no release notes at $notes"
  [ -z "$(git status --porcelain)" ] || die "the working tree has uncommitted changes; commit them (and rebuild) first"
  git fetch -q origin
  [ -n "$(git branch -r --contains "$sha")" ] || die "the current commit isn't on GitHub yet; push it first"
  if gh release view "v$v" > /dev/null 2>&1; then
    die "release v$v already exists"
  fi
  (cd "$out" && sha256sum --quiet -c SHA256SUMS) || die "the files in $out don't match SHA256SUMS; rebuild"

  echo "About to publish v$v at commit ${sha:0:7} with:"
  ls -1 "$out" | sed 's/^/  /'
  if [ -z "$yes" ]; then
    read -r -p "Publish? [y/N] " answer
    [[ "$answer" =~ ^[Yy] ]] || die "not published"
  fi
  gh release create "v$v" --target "$sha" --title "Markdown Cornell Notes $v" --notes-file "$notes" "$out"/*
}

case "${1:-}" in
  bump) bump "${2:-}" ;;
  build)
    shift
    build "$@"
    ;;
  publish) publish "${2:-}" ;;
  *)
    sed -n '2,/^set -euo/p' "$0" | sed -e '$d' -e 's/^# \{0,1\}//'
    exit 2
    ;;
esac
