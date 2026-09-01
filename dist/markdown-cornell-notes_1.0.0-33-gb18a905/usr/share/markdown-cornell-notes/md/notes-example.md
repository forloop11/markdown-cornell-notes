# Text Formatting

Welcome to the jungle. We've got fun and games.

^1 This is my question for Cue on page 1

^1 This is my question for Cue on page 1 on a new line

^^1 This is my summary for page 1

<!-- Cue-column text: a line of the form "^<page> <text>" (see the ^1
     line above) adds <text> to the ruled cue column of that page number
     instead of the main notes panel, e.g. for questions or keywords next
     to the notes they relate to. It's stripped out here, not printed as
     a paragraph. -->

<!-- Summary-band text: a line of the form "^^<page> <text>" (see the ^^1
     line above) adds <text> to that page's ruled summary band (the strip
     at the bottom of the page) instead. Same stripping as above. -->

**Bold**, *italic*, ***bold italic***, `inline code`, and ~~strikethrough~~.

# Lists

- Bullet item
- Another item
    - Nested bullet
        1. Nested numbered item
        2. Second nested numbered item
- Back to top level

1. First
2. Second
3. Third

Task list:

- [x] Completed task
- [ ] Open task

# Blockquote

> A quoted line
> that continues here.

# Code

Indented code block:

    echo "indented code block"

Fenced code block, no language tag:

```
plain fenced code
second line
```

Fenced code block, with a language tag:

```python
def hello():
    print("hi")
```

# Table

| Name   | Value  |
|:------:|-------:|
| a      | 1      |
| b      | 2      |

# Math

Inline math: $E = mc^2$.

Display math:

$$\int_0^1 x^2\,dx = \frac{1}{3}$$

# Links, Images, Autolinks

<https://example.com>

![Tux](assets/tux.jpg){width=75px}

# Misc

Horizontal rule:

---

Definition list:

Term
:   Definition of the term.

Superscript/subscript: H~2~O and x^2^.

<!-- Footnotes are intentionally omitted: \footnote inside cornellFlow's
     \vsplit-based pagination silently drops the footnote text -- the
     marker renders, the note text vanishes with no build error. This is
     an architectural limitation of cornellFlow, not a pandoc issue. -->

^2 This is my question for Cue on page 2
^^2 This is my summary for page 2

^^2 Verified with scratch tests outside the repo: realistic short summaries stay in column A with no warnings; deliberately long text correctly overflows into column B; and an extreme stress case (6 long items, more than 2 columns can hold) still degrades gracefully — one benign "overfull" warning, no crash, no data loss beyond the documented 2-column limit.

^^2 Verified with scratch tests outside the repo: realistic short summaries stay in column A with no warnings; deliberately long text correctly overflows into column B; and an extreme stress case (6 long items, more than 2 columns can hold) still degrades gracefully — one benign "overfull" warning, no crash, no data loss beyond the documented 2-column limit.
