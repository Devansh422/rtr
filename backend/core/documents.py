"""Generating downloadable documents: RTI applications, representations, certificates.

DEPENDENCY DECISION, because it looks like an omission otherwise. §5 lists
WeasyPrint/ReportLab for PDF, and neither is used here. Two reasons:

1. **Devanagari.** These documents are bilingual by requirement -- an RTI
   application to a Maharashtra PIO may need to be in Marathi or Hindi. Both
   Python PDF paths need a Devanagari-capable font bundled and, for correct
   conjunct rendering, a shaping engine. WeasyPrint pulls Pango/cairo native
   libraries, which do not fit a Vercel Python function; ReportLab renders
   Devanagari as broken glyph sequences without HarfBuzz. A PDF that mangles the
   applicant's own language is worse than no PDF.
2. **What the user actually needs.** An RTI application has to be *edited* (the
   applicant fills in specifics), then printed and signed. A DOCX is the useful
   artefact, and DOCX is a zip of XML -- writable with the standard library, no
   dependency, full Unicode, no font embedding problem.

So: DOCX for editing, and a print-optimised HTML view whose "Save as PDF" goes
through the browser's own text engine, which shapes Devanagari correctly and
costs nothing. If a server-rendered PDF is later genuinely required, it belongs
on the Render worker (§5) where native libraries are available, behind the same
function signatures used here.
"""

from dataclasses import dataclass, field
from io import BytesIO
from typing import Literal, Optional
from xml.sax.saxutils import escape
import zipfile

Align = Literal["left", "center", "right", "both"]


@dataclass
class Block:
    """One paragraph-level element. Deliberately small: these documents are
    letters and forms, not brochures."""

    text: str = ""
    kind: Literal["heading", "subheading", "para", "bullet", "spacer", "pagebreak"] = "para"
    bold: bool = False
    italic: bool = False
    align: Align = "left"


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------
_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

# `w:cs` is the complex-script font and is the line that makes Devanagari render
# as Devanagari rather than as boxes on a default Word install.
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Nirmala UI"/>
      <w:sz w:val="22"/><w:szCs w:val="22"/>
    </w:rPr></w:rPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="200" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph">
    <w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:ind w:left="720"/><w:spacing w:after="80"/></w:pPr>
  </w:style>
</w:styles>"""

_ALIGN_MAP = {"left": "left", "center": "center", "right": "right", "both": "both"}


def _run(text: str, *, bold: bool, italic: bool) -> str:
    props = ""
    if bold or italic:
        props = "<w:rPr>" + ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "") + "</w:rPr>"
    # xml:space="preserve" matters: without it Word discards the leading spaces
    # that keep a form's dotted-line fields aligned.
    return f'<w:r>{props}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _paragraph_xml(block: Block) -> str:
    if block.kind == "pagebreak":
        return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
    if block.kind == "spacer":
        return "<w:p/>"

    style = {
        "heading": "Heading1",
        "subheading": "Heading2",
        "bullet": "ListParagraph",
    }.get(block.kind, "Normal")

    props = f'<w:pStyle w:val="{style}"/>'
    if block.align != "left":
        props += f'<w:jc w:val="{_ALIGN_MAP[block.align]}"/>'

    text = f"•  {block.text}" if block.kind == "bullet" else block.text
    bold = block.bold or block.kind in ("heading", "subheading")

    # A blank line inside a block becomes a real paragraph break rather than a
    # literal newline, which Word would otherwise collapse.
    runs = "".join(
        _run(line, bold=bold, italic=block.italic) + ("<w:br/>" if i else "")
        for i, line in enumerate(text.split("\n"))
    )
    return f"<w:p><w:pPr>{props}</w:pPr>{runs}</w:p>"


# A4 portrait with ~1 inch margins, in twentieths of a point.
_SECT_PR = (
    '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
    '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
    'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>'
)


def build_docx(blocks: list[Block]) -> bytes:
    """A valid .docx from paragraph blocks, using only the standard library."""
    body = "".join(_paragraph_xml(b) for b in blocks)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}{_SECT_PR}</w:body></w:document>"
    )

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        # [Content_Types].xml must be the first entry for some readers.
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/_rels/document.xml.rels", _DOC_RELS)
        archive.writestr("word/styles.xml", _STYLES)
    return buffer.getvalue()


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# --------------------------------------------------------------------------
# Print view (browser -> PDF)
# --------------------------------------------------------------------------
_PRINT_CSS = """
@page { size: A4; margin: 20mm 18mm; }
* { box-sizing: border-box; }
body {
  font-family: "Segoe UI", system-ui, -apple-system, "Nirmala UI", "Noto Sans Devanagari", sans-serif;
  color: #101828; line-height: 1.65; font-size: 11.5pt;
  max-width: 174mm; margin: 0 auto; padding: 12mm 0;
}
h1 { font-size: 17pt; margin: 0 0 6mm; line-height: 1.3; }
h2 { font-size: 13pt; margin: 8mm 0 3mm; }
p { margin: 0 0 3.5mm; }
ul { margin: 0 0 4mm; padding-left: 7mm; }
li { margin-bottom: 1.5mm; }
.right { text-align: right; }
.center { text-align: center; }
.pagebreak { page-break-before: always; }
.hint {
  background: #f2f4f7; border-left: 3px solid #98a2b3; padding: 4mm 5mm;
  font-size: 10pt; color: #475467; margin: 0 0 6mm; border-radius: 2px;
}
.toolbar { margin: 0 0 8mm; display: flex; gap: 8px; }
.toolbar button {
  font: inherit; font-size: 10pt; padding: 8px 14px; border-radius: 6px;
  border: 1px solid #d0d5dd; background: #fff; cursor: pointer;
}
.toolbar button.primary { background: #175cd3; border-color: #175cd3; color: #fff; font-weight: 600; }
@media print { .toolbar, .hint { display: none !important; } body { padding: 0; } }
"""


def render_print_html(title: str, blocks: list[Block], *, hint: Optional[str] = None) -> str:
    """A standalone printable page.

    "Save as PDF" in the browser's print dialog produces a correctly shaped
    Devanagari PDF at zero cost, which is the whole reason this exists instead
    of a server-side renderer (see the module docstring).
    """
    parts: list[str] = []
    for block in blocks:
        text = escape(block.text)
        cls = f' class="{block.align}"' if block.align in ("center", "right") else ""
        if block.kind == "heading":
            parts.append(f"<h1{cls}>{text}</h1>")
        elif block.kind == "subheading":
            parts.append(f"<h2{cls}>{text}</h2>")
        elif block.kind == "bullet":
            parts.append(f"<ul><li>{text}</li></ul>")
        elif block.kind == "spacer":
            parts.append("<p>&nbsp;</p>")
        elif block.kind == "pagebreak":
            parts.append('<div class="pagebreak"></div>')
        else:
            body = text.replace("\n", "<br>")
            if block.bold:
                body = f"<strong>{body}</strong>"
            parts.append(f"<p{cls}>{body}</p>")

    hint_html = f'<div class="hint">{escape(hint)}</div>' if hint else ""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{escape(title)}</title>
<style>{_PRINT_CSS}</style>
</head><body>
<div class="toolbar">
  <button class="primary" onclick="window.print()">Print / Save as PDF</button>
</div>
{hint_html}
{''.join(parts)}
</body></html>"""


# --------------------------------------------------------------------------
# Shared building block
# --------------------------------------------------------------------------
@dataclass
class DocumentDraft:
    """A generated document before it is serialised to any format.

    Every generator in modules/tools returns one of these, so a caller chooses
    DOCX or print-HTML at the last moment and the two can never drift apart.
    """

    title: str
    filename: str
    blocks: list[Block] = field(default_factory=list)
    hint: Optional[str] = None

    def docx(self) -> bytes:
        return build_docx(self.blocks)

    def html(self) -> str:
        return render_print_html(self.title, self.blocks, hint=self.hint)

    def plain_text(self) -> str:
        """For emailing the draft and for the on-screen preview."""
        lines: list[str] = []
        for block in self.blocks:
            if block.kind == "pagebreak":
                lines.append("\n---\n")
            elif block.kind == "spacer":
                lines.append("")
            elif block.kind == "bullet":
                lines.append(f"  - {block.text}")
            elif block.kind in ("heading", "subheading"):
                lines.extend([block.text, "=" * min(len(block.text), 60)])
            else:
                lines.append(block.text)
        return "\n".join(lines)
