#!/usr/bin/env python3
"""Convert a header yaml (e.g. yaml/notes.yaml) into build/cornell-header.tex.

Supports the flat "key: value" subset of YAML used for the Cornell notes
header fields (topic, date, attendees, time) -- no nesting, lists, or
multi-line values. Avoids a PyYAML dependency since the header data is
always this simple.

An optional "layout" field picks the page layout: "cornell" (the
default, also used when it's blank or missing) or "plain" (see
settings/template.tex's \\ifcnplainlayout).

Usage (from the repo root): python3 scripts/yaml_to_header.py [input.yaml] [output.tex]
"""
import sys

from simple_yaml import parse_yaml, write_generated

FIELD_MACROS = {
    "topic": "cnHdrTopic",
    "date": "cnHdrDate",
    "attendees": "cnHdrAttendees",
    "time": "cnHdrTime",
    "timezone": "cnHdrTimezone",
    "location": "cnHdrLocation",
}

# "layout" values, and the \if switch each one sets in the template ("" for
# none -- the template's default, the Cornell page).
LAYOUTS = {
    "": "",
    "cornell": "",
    "plain": "\\cnplainlayouttrue",
}

LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(value):
    """Escape every LaTeX-special character in `value` (see LATEX_SPECIALS)
    so it can be typeset as literal text.
    """
    return "".join(LATEX_SPECIALS.get(ch, ch) for ch in value)


def main():
    """Generate a header .tex file from the yaml file named on the
    command line (default "yaml/notes.yaml"), writing it to the output
    path named on the command line (default "build/cornell-header.tex").
    """
    in_path = sys.argv[1] if len(sys.argv) > 1 else "yaml/notes.yaml"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "build/cornell-header.tex"

    fields = parse_yaml(in_path)

    unknown = set(fields) - set(FIELD_MACROS) - {"layout"}
    if unknown:
        raise ValueError(f"{in_path}: unrecognized field(s): {', '.join(sorted(unknown))}")
    layout = fields.get("layout", "").lower()
    if layout not in LAYOUTS:
        raise ValueError(f"{in_path}: layout must be cornell or plain, got: {fields['layout']!r}")

    lines = [
        f"% Generated from {in_path} by scripts/yaml_to_header.py -- do not edit by hand.",
    ]
    for key, macro in FIELD_MACROS.items():
        value = escape_latex(fields.get(key, ""))
        lines.append(f"\\renewcommand{{\\{macro}}}{{{value}}}")
    if LAYOUTS[layout]:
        lines.append(LAYOUTS[layout])

    write_generated(out_path, lines)


if __name__ == "__main__":
    main()
