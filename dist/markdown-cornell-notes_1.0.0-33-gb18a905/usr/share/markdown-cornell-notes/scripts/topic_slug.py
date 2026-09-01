#!/usr/bin/env python3
"""Derive the output PDF's base filename (the latexmk jobname) from a
header yaml's `topic`, `date`, and `location` fields.

Each field is slugified separately -- runs of characters that aren't safe
to use in a filename (spaces, slashes, punctuation, ...) collapse to a
single hyphen -- then joined with an underscore, so e.g. topic "Weekly
Sync" + date 2026-08-23 + location "Zoom" becomes
"Weekly-Sync_2026-08-23_Zoom" and the PDF comes out as
Weekly-Sync_2026-08-23_Zoom.pdf. `location` is optional -- a blank/missing
one is dropped rather than leaving a trailing underscore.

Usage (from the repo root): python3 scripts/topic_slug.py [yaml/notes.yaml]
"""
import re
import sys

from simple_yaml import parse_yaml

UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def slugify(value):
    return UNSAFE_RE.sub("-", value.strip()).strip("-")


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else "yaml/notes.yaml"
    fields = parse_yaml(in_path)

    parts = [slugify(fields.get(key, "")) for key in ("topic", "date", "location")]
    parts = [part for part in parts if part]

    print("_".join(parts) if parts else "cornell-notes")


if __name__ == "__main__":
    main()
