# Text Formatting

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

| Name | Value |
|------|-------|
| a    | 1     |
| b    | 2     |

# Math

Inline math: $E = mc^2$.

Display math:

$$\int_0^1 x^2\,dx = \frac{1}{3}$$

# Links, Images, Autolinks

See the [reference notes](assets/reference-notes.txt) for background.

<https://example.com>

![Tux](assets/tux.jpg){width=50pt}

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
