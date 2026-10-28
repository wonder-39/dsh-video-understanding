# -*- coding: utf-8 -*-
"""Word 交付物的复用库：中文字体、标题、编号表图、页码、要点列表。

用法（任何对话里）：
    import sys
    sys.path.insert(0, r"C:\\Users\\jack\\.dsh\\skills\\video-understanding\\scripts")
    from docx_helpers import Doc

    d = Doc(r"D:\\Desktop\\xxx\\report.docx", image_dir=r"D:\\Desktop\\xxx\\frames")
    d.h1("总览（标准档）")
    d.table(["素材", "类型", "一句话总结"], [...], caption="总览", widths=[5, 3, 8])
    d.image("01.png", "标题页：把矛盾写成标题")
    d.h1("三、重点突出（对比）")
    d.num_list(["红开总时长 650 小时，蓝开 850 小时", "…"])
    d.save()

约定：
- 表格题注在图上方，写作「表-N　说明」；图片题注在图下方，写作「图-N　说明」。
- 编号在整份文档内连续，跨章节不重置。
- 页脚固定为「第 X 页 共 Y 页」。
"""
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = "微软雅黑"
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
BODY = RGBColor(0x2E, 0x2E, 0x2E)
MUTED = RGBColor(0x59, 0x59, 0x59)
CAPTION = RGBColor(0x40, 0x40, 0x40)


class Doc:
    def __init__(self, path, footer_text=None, image_dir=".", font=FONT):
        self.path = path
        self.image_dir = image_dir
        self.font = font
        self._tbl_no = 0
        self._fig_no = 0
        self.doc = Document()
        self._setup_page()
        self._setup_footer()

    # ---------- 初始化 ----------
    def _setup_page(self):
        sec = self.doc.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.4)
        sec.top_margin = Cm(2.2)
        sec.bottom_margin = Cm(2.0)
        style = self.doc.styles["Normal"]
        style.font.name = self.font
        style.font.size = Pt(10.5)
        style.element.rPr.rFonts.set(qn("w:eastAsia"), self.font)

    def _field(self, paragraph, code, size=8, color=MUTED):
        """插入一个 Word 域（PAGE / NUMPAGES），由渲染器求值。"""
        run = paragraph.add_run()
        begin = OxmlElement("w:fldChar")
        begin.set(qn("w:fldCharType"), "begin")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = f" {code} "
        sep = OxmlElement("w:fldChar")
        sep.set(qn("w:fldCharType"), "separate")
        text = OxmlElement("w:t")
        text.text = "1"
        end = OxmlElement("w:fldChar")
        end.set(qn("w:fldCharType"), "end")
        run._r.append(begin)
        run._r.append(instr)
        run._r.append(sep)
        run._r.append(text)
        run._r.append(end)
        self._font(run, size, False, color)
        return run

    def _setup_footer(self):
        p = self.doc.sections[0].footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._font(p.add_run("第 "), 8, False, MUTED)
        self._field(p, "PAGE")
        self._font(p.add_run(" 页 共 "), 8, False, MUTED)
        self._field(p, "NUMPAGES")
        self._font(p.add_run(" 页"), 8, False, MUTED)

    def _font(self, run, size=None, bold=None, color=None):
        run.font.name = self.font
        run._element.rPr.rFonts.set(qn("w:eastAsia"), self.font)
        if size is not None:
            run.font.size = Pt(size)
        if bold is not None:
            run.font.bold = bold
        if color is not None:
            run.font.color.rgb = color

    # ---------- 编号 ----------
    def table_label(self):
        return f"表-{self._tbl_no + 1}"

    def fig_label(self):
        return f"图-{self._fig_no + 1}"

    # ---------- 内容 ----------
    def cover(self, tag, title, subtitle):
        self.para(tag, 9, False, MUTED, WD_ALIGN_PARAGRAPH.CENTER, before=18)
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(4)
        self._font(p.add_run(title), 20, True, ACCENT)
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        self._font(p.add_run(subtitle), 12, True, BODY)

    def para(self, text="", size=10.5, bold=False, color=None, align=None,
             after=6, before=0):
        p = self.doc.add_paragraph()
        if align is not None:
            p.alignment = align
        pf = p.paragraph_format
        pf.space_after = Pt(after)
        pf.space_before = Pt(before)
        pf.line_spacing = 1.35
        if text:
            self._font(p.add_run(text), size, bold, color)
        return p

    def note(self, text):
        """小字补充说明（灰色）。"""
        return self.para(text, 9, False, MUTED, after=4)

    def quote(self, text):
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.8)
        pf.space_before = Pt(4)
        pf.space_after = Pt(4)
        pf.line_spacing = 1.3
        self._font(p.add_run(text), 10.5, True, ACCENT)
        return p

    def h1(self, text):
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_before = Pt(16)
        pf.space_after = Pt(6)
        pf.keep_with_next = True          # 防孤行
        self._font(p.add_run(text), 15, True, ACCENT)
        pPr = p._p.get_or_add_pPr()
        pbdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "2")
        bottom.set(qn("w:color"), "1F4E79")
        pbdr.append(bottom)
        pPr.append(pbdr)
        return p

    def h2(self, text):
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_before = Pt(12)
        pf.space_after = Pt(4)
        pf.keep_with_next = True
        self._font(p.add_run(text), 12, True, BODY)
        return p

    def num_list(self, items, size=10.5, start=1):
        """编号列点：1. 2. 3.，悬挂缩进，行距紧凑。"""
        for i, item in enumerate(items, start):
            p = self.doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Cm(0.75)
            pf.first_line_indent = Cm(-0.75)
            pf.space_after = Pt(4)
            pf.line_spacing = 1.3
            self._font(p.add_run(f"{i}. "), size, True, ACCENT)
            self._font(p.add_run(str(item)), size, False, BODY)

    def image(self, filename, caption="", width_cm=15.0):
        import os
        self._fig_no += 1
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        p.add_run().add_picture(os.path.join(self.image_dir, filename),
                                width=Cm(width_cm))
        c = self.doc.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraph_format.space_after = Pt(10)
        self._font(c.add_run(f"图-{self._fig_no}　{caption}".rstrip("　")),
                   9, False, CAPTION)
        return f"图-{self._fig_no}"

    def table(self, headers, rows, widths=None, fill="1F4E79", caption=""):
        # 题注在表上方
        if caption:
            cp = self.doc.add_paragraph()
            cp.paragraph_format.space_before = Pt(8)
            cp.paragraph_format.space_after = Pt(3)
            cp.paragraph_format.keep_with_next = True
            self._font(cp.add_run(f"表-{self._tbl_no + 1}　{caption}"),
                       9, True, CAPTION)

        t = self.doc.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        self._tbl_no += 1
        # 表头跨页重复
        trPr = t.rows[0]._tr.get_or_add_trPr()
        th = OxmlElement("w:tblHeader")
        th.set(qn("w:val"), "true")
        trPr.append(th)
        for i, h in enumerate(headers):
            cell = t.rows[0].cells[i]
            cell.text = ""
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._font(p.add_run(h), 9.5, True, RGBColor(0xFF, 0xFF, 0xFF))
            shd = OxmlElement("w:shd")
            shd.set(qn("w:fill"), fill)
            cell._tc.get_or_add_tcPr().append(shd)
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ""
                p = cells[i].paragraphs[0]
                p.paragraph_format.space_after = Pt(2)
                self._font(p.add_run(str(v)), 9.5)
        # 行不跨页切断
        for r in t.rows:
            tp = r._tr.get_or_add_trPr()
            cs = OxmlElement("w:cantSplit")
            cs.set(qn("w:val"), "true")
            tp.append(cs)
        if widths:
            # autofit 会覆盖单元格宽度，必须改成固定布局，否则列宽不生效
            t.autofit = False
            tblPr = t._tbl.tblPr
            layout = OxmlElement("w:tblLayout")
            layout.set(qn("w:type"), "fixed")
            tblPr.append(layout)
            for i, w in enumerate(widths):
                t.columns[i].width = Cm(w)
            for r in t.rows:
                for i, w in enumerate(widths):
                    r.cells[i].width = Cm(w)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)
        return f"表-{self._tbl_no}"

    def save(self):
        self.doc.save(self.path)
        return self.path
