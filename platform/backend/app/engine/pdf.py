"""Minimal, dependency-free PDF writer (text reports).

Produces a valid multi-page A4 PDF with Helvetica / Helvetica-Bold from
Markdown-flavoured text. No system libraries, no network — the same
deterministic local-first guarantee as the rest of the engine. Output is a
bytes object; the reports layer wraps it in a base64 data URL for storage.
"""
from __future__ import annotations

import textwrap

PAGE_W, PAGE_H = 595.0, 842.0  # A4, points
MARGIN = 50.0
BODY_PT = 10.0
BODY_LEAD = 13.5
LINES_PER_PAGE = int((PAGE_H - 2 * MARGIN) / BODY_LEAD)


def _escape(s: str) -> str:
    return (s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)"))


def _md_lines(md: str) -> list[tuple[str, str]]:
    """Flatten markdown to (style, text) pairs: h1/h2/h3/bullet/text/blank."""
    out: list[tuple[str, str]] = []
    in_code = False
    for raw in (md or "").splitlines():
        s = raw.rstrip()
        if s.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            out.append(("code", s))
            continue
        if s.startswith("### "):
            out.append(("h3", s[4:].strip()))
        elif s.startswith("## "):
            out.append(("h2", s[3:].strip()))
        elif s.startswith("# "):
            out.append(("h1", s[2:].strip()))
        elif s.strip().startswith(("- ", "* ")):
            out.append(("bullet", s.strip()[2:]))
        elif s.strip() == "---":
            out.append(("rule", ""))
        else:
            out.append(("text", s))
    return out


def _wrap(text: str, width: int) -> list[str]:
    if not text:
        return [""]
    return textwrap.wrap(text, width=width) or [""]


def _content_stream(lines: list[tuple[str, str]]) -> str:
    """One page's content stream. Emits absolute-position Tm per line."""
    parts: list[str] = []
    y = PAGE_H - MARGIN
    for style, text in lines:
        if style == "blank":
            y -= BODY_LEAD * 0.6
            continue
        if style == "rule":
            y -= BODY_LEAD
            continue
        if style == "h1":
            font, size, lead, gap_before = "F2", 16.0, 22.0, 8.0
        elif style == "h2":
            font, size, lead, gap_before = "F2", 13.0, 18.0, 6.0
        elif style == "h3":
            font, size, lead, gap_before = "F2", 11.0, 15.0, 5.0
        elif style == "bullet":
            font, size, lead, gap_before = "F1", BODY_PT, BODY_LEAD, 0.0
        elif style == "code":
            font, size, lead, gap_before = "F1", 9.0, 12.0, 0.0
        else:  # text
            font, size, lead, gap_before = "F1", BODY_PT, BODY_LEAD, 0.0

        width_chars = 96 if style != "code" else 108
        segs = _wrap(text, width_chars)
        prefix = "•  " if style == "bullet" else ""
        for i, seg in enumerate(segs):
            y -= gap_before if i == 0 else 0
            y -= lead if i == 0 else size + 2.5
            parts.append(f"BT /{font} {size:g} Tf 1 0 0 1 {MARGIN:g} {y:.2f} Tm "
                         f"({ _escape(prefix + seg) }) Tj ET")
    return "\n".join(parts)


def _paginate(md: str) -> list[list[tuple[str, str]]]:
    pages: list[list[tuple[str, str]]] = []
    cur: list[tuple[str, str]] = []
    used = 0
    for style, text in _md_lines(md):
        width_chars = 96 if style not in ("code",) else 108
        n = max(1, len(_wrap(text, width_chars)))
        lead = {"h1": 22, "h2": 18, "h3": 15, "code": 12}.get(style, BODY_LEAD)
        if cur and used + n * lead > (PAGE_H - 2 * MARGIN):
            pages.append(cur)
            cur, used = [], 0
        cur.append((style, text))
        used += n * lead
    if cur or not pages:
        pages.append(cur)
    return pages[:200]  # documented hard cap


def render_pdf(title: str, markdown: str) -> bytes:
    """Build the PDF bytes for a report (title on the first page)."""
    pages = _paginate(markdown)
    # prepend a title block to page 1
    pages[0] = [("h1", title), ("text", ""), *pages[0]]

    objects: list[bytes] = []  # 1-based indexing handled below
    n = len(pages)
    # object numbers: 1 catalog, 2 pages, 3..(2+n) page objs,
    # then (3+n) F1, (4+n) F2, then content streams (5+n+i)
    page_obj_nums = [3 + i for i in range(n)]
    f1_num, f2_num = 3 + n, 4 + n
    content_nums = [5 + n + i for i in range(n)]

    def obj(num: int, body: bytes) -> None:
        while len(objects) < num:
            objects.append(b"")
        objects[num - 1] = body

    kids = " ".join(f"{p} 0 R" for p in page_obj_nums)
    obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    obj(2, f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    for i, pnum in enumerate(page_obj_nums):
        body = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W:g} {PAGE_H:g}] "
                f"/Resources << /Font << /F1 {f1_num} 0 R /F2 {f2_num} 0 R >> >> "
                f"/Contents {content_nums[i]} 0 R >>")
        obj(pnum, body.encode())
    obj(f1_num, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    obj(f2_num, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    for i, cnum in enumerate(content_nums):
        stream = _content_stream(pages[i]).encode("latin-1", "replace")
        obj(cnum, b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for body in objects:
        offsets.append(len(out))
        out += str(len(offsets)).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(offsets) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n").encode()
    return bytes(out)
