#!/usr/bin/env python3
"""Convert settings/page.yaml into build/cornell-page-settings.tex.

Controls page geometry (paper size, margin), header/footer/cue-column
sizing (as fractions of the page), and spacing (rule spacing, padding,
border inset) -- the "TEMPLATE CONFIGURATION" knobs in etc/cornell-notes.tex.
Field values are passed through to LaTeX as-is (lengths and decimals,
not prose), so no escaping is needed.

Usage (from the repo root): python3 scripts/yaml_to_settings.py [input.yaml] [output.tex]
"""
import sys

from simple_yaml import parse_yaml, write_generated

GEOMETRY_FIELDS = ("paper", "margin")
FRAC_MACROS = {
    "header_height": "cnHeaderHeightFrac",
    "footer_height": "cnFooterHeightFrac",
    "cue_width": "cnCueWidthFrac",
}
LENGTH_MACROS = {
    "rule_spacing": "cnRuleSpacing",
    "padding": "cnPad",
    "border_inset": "cnBorderInset",
}
KNOWN_FIELDS = set(GEOMETRY_FIELDS) | set(FRAC_MACROS) | set(LENGTH_MACROS)


def main():
    in_path = sys.argv[1] if len(sys.argv) > 1 else "settings/page.yaml"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "build/cornell-page-settings.tex"

    fields = parse_yaml(in_path)

    unknown = set(fields) - KNOWN_FIELDS
    if unknown:
        raise ValueError(f"{in_path}: unrecognized field(s): {', '.join(sorted(unknown))}")

    lines = [
        f"% Generated from {in_path} by scripts/yaml_to_settings.py -- do not edit by hand.",
    ]

    geometry_opts = [key for key in GEOMETRY_FIELDS if fields.get(key)]
    if geometry_opts:
        opts = [fields[key] if key == "paper" else f"{key}={fields[key]}" for key in geometry_opts]
        lines.append(f"\\geometry{{{','.join(opts)}}}")

    for key, macro in FRAC_MACROS.items():
        if key in fields:
            lines.append(f"\\renewcommand{{\\{macro}}}{{{fields[key]}}}")

    for key, macro in LENGTH_MACROS.items():
        if key in fields:
            lines.append(f"\\setlength{{\\{macro}}}{{{fields[key]}}}")

    write_generated(out_path, lines)


if __name__ == "__main__":
    main()
