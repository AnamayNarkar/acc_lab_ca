"""Helpers that mirror the template's formatting (Times New Roman 12, justified body, grey-header tables, centred captions)."""
import copy, re
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH as AL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, Emu

class Doc:
    def __init__(self, template):
        self.d = Document(template)
        body = self.d.element.body
        for el in list(body):
            if el.tag != qn("w:sectPr"): body.remove(el)
        self.figs, self.tabs, self.heads = [], [], []

    # --- runs with **bold** and `code` and _italic_ markup
    def _runs(self, p, text, size=None, bold=False, italic=False):
        for part in re.split(r"(\*\*.+?\*\*|`.+?`)", text):
            if not part: continue
            if part.startswith("**"): r = p.add_run(part[2:-2]); r.bold = True
            elif part.startswith("`"): r = p.add_run(part[1:-1]); r.font.name = "Courier New"; r._element.rPr.rFonts.set(qn("w:hAnsi"), "Courier New"); r.font.size = Pt(10)
            else: r = p.add_run(part); r.bold = bold or None
            if italic: r.italic = True
            if size and not part.startswith("`"): r.font.size = Pt(size)

    def para(self, text, align="j", size=None, bold=False, italic=False, after=7, before=0, spacing=1.4167, keep=False):
        p = self.d.add_paragraph(style="Normal")
        p.alignment = {"j": AL.JUSTIFY, "c": AL.CENTER, "l": AL.LEFT}[align]
        pf = p.paragraph_format; pf.space_after = Pt(after); pf.space_before = Pt(before); pf.line_spacing = spacing
        if keep: pf.keep_with_next = True
        self._runs(p, text, size, bold, italic); return p

    def h1(self, text, page_break=True, center=False):
        p = self.d.add_paragraph(style="Heading 1"); p.add_run(text)
        if page_break: p.paragraph_format.page_break_before = True
        if center: p.alignment = AL.CENTER
        self.heads.append((1, text)); return p

    def h2(self, text):
        p = self.d.add_paragraph(style="Heading 2"); p.add_run(text); self.heads.append((2, text)); return p

    def bullet(self, text, num=None):
        p = self.d.add_paragraph(style="List Paragraph"); p.alignment = AL.JUSTIFY
        pf = p.paragraph_format; pf.left_indent = Cm(1.0); pf.first_line_indent = Cm(-0.6); pf.space_after = Pt(4); pf.line_spacing = 1.4167
        self._runs(p, (f"{num}. " if num else "•  ") + text); return p

    def code(self, lines):
        for ln in lines:
            p = self.d.add_paragraph(style="Normal"); pf = p.paragraph_format; pf.space_after = Pt(0); pf.left_indent = Cm(0.6)
            r = p.add_run(ln); r.font.name = "Courier New"; r._element.rPr.rFonts.set(qn("w:hAnsi"), "Courier New"); r.font.size = Pt(9)
        self.d.add_paragraph(style="Normal").paragraph_format.space_after = Pt(4)

    def caption(self, text, kind):
        p = self.para(text, align="c", size=11, after=10, spacing=1.15)
        return p

    def table(self, header, rows, widths_cm, caption, align_right_from=1, font=10):
        n = len(self.tabs) + 1; self.tabs.append(caption)
        self.para(f"Table {n}: {caption}", align="c", size=11, after=4, before=6, spacing=1.15, keep=True)
        t = self.d.add_table(rows=1 + len(rows), cols=len(header)); t.autofit = False
        tblPr = t._tbl.tblPr
        borders = OxmlElement("w:tblBorders")
        for e in ("top", "left", "bottom", "right", "insideH", "insideV"):
            b = OxmlElement(f"w:{e}"); b.set(qn("w:val"), "single"); b.set(qn("w:sz"), "4"); b.set(qn("w:space"), "0"); b.set(qn("w:color"), "808080"); borders.append(b)
        tblPr.append(borders)
        for ri, row in enumerate([header] + rows):
            tr = t.rows[ri]
            trPr = tr._tr.get_or_add_trPr(); cs = OxmlElement("w:cantSplit"); trPr.append(cs)
            if ri == 0: trPr.append(OxmlElement("w:tblHeader"))
            for ci, val in enumerate(row):
                cell = tr.cells[ci]; cell.width = Cm(widths_cm[ci])
                tcPr = cell._tc.get_or_add_tcPr()
                mar = OxmlElement("w:tcMar")
                for side, w in (("top", 60), ("left", 100), ("bottom", 60), ("right", 100)):
                    m = OxmlElement(f"w:{side}"); m.set(qn("w:w"), str(w)); m.set(qn("w:type"), "dxa"); mar.append(m)
                tcPr.append(mar)
                if ri == 0:
                    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "D9D9D9"); tcPr.append(shd)
                p = cell.paragraphs[0]; p.paragraph_format.space_after = Pt(0); p.paragraph_format.line_spacing = 1.0
                if ci >= align_right_from and ri > 0 and re.match(r"^[\$\-\d\.,%\s]+[kMb%]?$", str(val).strip() or "x"): p.alignment = AL.RIGHT
                self._runs(p, str(val), size=font, bold=(ri == 0))
        self.d.add_paragraph(style="Normal").paragraph_format.space_after = Pt(6)
        return n

    def figure(self, path, width_cm, caption):
        n = len(self.figs) + 1; self.figs.append(caption)
        p = self.d.add_paragraph(style="Normal"); p.alignment = AL.CENTER; p.paragraph_format.keep_with_next = True; p.paragraph_format.space_after = Pt(4)
        p.add_run().add_picture(str(path), width=Cm(width_cm))
        self.para(f"Figure {n}: {caption}", align="c", size=11, after=10, spacing=1.15)
        return n

    def page_break(self):
        self.d.add_paragraph().add_run().add_break(__import__("docx").enum.text.WD_BREAK.PAGE)

    def save(self, path): self.d.save(path)
