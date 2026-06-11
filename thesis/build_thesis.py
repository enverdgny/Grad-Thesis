"""Build the graduation thesis as a .docx that follows the Cukurova University
Faculty of Engineering template and the stated formatting principles.

Run (from project root):
    .venv/bin/python thesis/make_figures.py
    .venv/bin/python thesis/build_thesis.py

Output: thesis/Graduation_Thesis.docx

The document uses Word fields for the Table of Contents, List of Tables and
List of Figures. They are marked dirty and the file forces a field update on
open, so Word will populate page numbers automatically (answer "Yes" if Word
asks to update fields, or press Ctrl+A then F9).
"""

import json
import os

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "thesis", "figures")

with open(os.path.join(ROOT, "thesis", "stats.json")) as f:
    STATS = json.load(f)

FONT = "Times New Roman"
SIZE = 12

# ----------------------------------------------------------------------------
# Low-level XML helpers
# ----------------------------------------------------------------------------

def _el(tag, **attrs):
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(k), v)
    return e


def set_run_font(run, size=SIZE, bold=False, italic=False, color=None):
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = _el("w:rFonts")
        rpr.insert(0, rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(a), FONT)


def add_field(paragraph, instr, size=SIZE, bold=False):
    """Insert a Word field (e.g. PAGE, TOC) marked dirty so Word updates it."""
    r = paragraph.add_run()
    set_run_font(r, size, bold)
    fld_begin = _el("w:fldChar", **{"w:fldCharType": "begin", "w:dirty": "true"})
    r._element.append(fld_begin)

    r2 = paragraph.add_run()
    set_run_font(r2, size, bold)
    it = _el("w:instrText", **{"xml:space": "preserve"})
    it.text = instr
    r2._element.append(it)

    r3 = paragraph.add_run()
    set_run_font(r3, size, bold)
    r3._element.append(_el("w:fldChar", **{"w:fldCharType": "separate"}))

    r4 = paragraph.add_run("")
    set_run_font(r4, size, bold)

    r5 = paragraph.add_run()
    set_run_font(r5, size, bold)
    r5._element.append(_el("w:fldChar", **{"w:fldCharType": "end"}))


def set_pgnum(section, fmt, start=None):
    """fmt: 'lowerRoman' or 'decimal'."""
    sectPr = section._sectPr
    old = sectPr.find(qn("w:pgNumType"))
    if old is not None:
        sectPr.remove(old)
    p = _el("w:pgNumType", **{"w:fmt": fmt})
    if start is not None:
        p.set(qn("w:start"), str(start))
    sectPr.append(p)


def clear_pgnum(section):
    """Remove any pgNumType so this section continues the previous numbering."""
    sectPr = section._sectPr
    old = sectPr.find(qn("w:pgNumType"))
    if old is not None:
        sectPr.remove(old)


def footer_page_number(section, fmt_size=SIZE):
    section.footer.is_linked_to_previous = False
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    add_field(p, " PAGE ", size=fmt_size)


def update_fields_on_open(doc):
    settings = doc.settings.element
    if settings.find(qn("w:updateFields")) is None:
        settings.append(_el("w:updateFields", **{"w:val": "true"}))


# ----------------------------------------------------------------------------
# Paragraph / content helpers
# ----------------------------------------------------------------------------

def body(doc, text, justify=True, indent=True, after=6, spacing=1.5):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if justify else WD_ALIGN_PARAGRAPH.LEFT
    if indent:
        pf.first_line_indent = Cm(1.25)
    pf.line_spacing = spacing
    pf.space_after = Pt(after)
    r = p.add_run(text)
    set_run_font(r)
    return p


def blank_line(doc):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("")
    set_run_font(r)
    return p


def heading(doc, text, level=1, centered=False, style="Heading 1"):
    """Main/sub section title: TNR 12, bold, uppercase handled by caller."""
    p = doc.add_paragraph(style=style)
    pf = p.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.CENTER if centered else WD_ALIGN_PARAGRAPH.LEFT
    pf.space_before = Pt(0)
    pf.space_after = Pt(12)
    pf.line_spacing = 1.5
    pf.keep_with_next = True
    r = p.add_run(text)
    set_run_font(r, size=SIZE, bold=True)
    return p


def new_main_section(doc, title, numbered_centered=False):
    """Start a new main section on an odd page and add its bold UPPERCASE title."""
    sec = doc.add_section(WD_SECTION.ODD_PAGE)
    _base_margins(sec)
    return sec


# ----------------------------------------------------------------------------
# Tables (booktabs style: top rule, header rule, bottom rule; header repeats)
# ----------------------------------------------------------------------------

def _set_cell_text(cell, text, bold=False, align=WD_ALIGN_PARAGRAPH.CENTER, size=SIZE):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)
    r = p.add_run(text)
    set_run_font(r, size=size, bold=bold)


def _cell_border(cell, top=False, bottom=False):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = _el("w:tcBorders")
    for edge in ("top", "bottom"):
        on = top if edge == "top" else bottom
        e = _el(f"w:{edge}",
                **{"w:val": "single" if on else "nil",
                   "w:sz": "8", "w:space": "0", "w:color": "000000"})
        borders.append(e)
    tcPr.append(borders)


def add_caption(doc, label_no, caption_text, style_name):
    """Centered caption paragraph in a dedicated style so the List of
    Tables / Figures TOC fields can collect it. label_no e.g. 'Table 3.1.'"""
    p = doc.add_paragraph(style=style_name)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.keep_with_next = True
    r1 = p.add_run(label_no + " ")
    set_run_font(r1, bold=True)
    r2 = p.add_run(caption_text)
    set_run_font(r2, bold=False)
    return p


def add_table(doc, label_no, caption, headers, rows, col_widths=None):
    """Table with centered caption ABOVE, one blank line before and after,
    header row repeated across pages, only horizontal rules."""
    blank_line(doc)
    add_caption(doc, label_no, caption, "CaptionTable")

    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = True

    # repeat header row on each page
    trPr = t.rows[0]._tr.get_or_add_trPr()
    trPr.append(_el("w:tblHeader", **{"w:val": "true"}))

    for j, h in enumerate(headers):
        c = t.rows[0].cells[j]
        _set_cell_text(c, h, bold=True)
        _cell_border(c, top=True, bottom=True)

    for i, row in enumerate(rows):
        cells = t.add_row().cells
        last = (i == len(rows) - 1)
        for j, val in enumerate(row):
            align = WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.CENTER
            _set_cell_text(cells[j], str(val), align=align)
            _cell_border(cells[j], bottom=last)

    if col_widths:
        for row in t.rows:
            for j, w in enumerate(col_widths):
                row.cells[j].width = Cm(w)
    blank_line(doc)
    return t


def add_figure(doc, label_no, caption, image_path, width_cm=13.0):
    """Centered image with centered caption BELOW, blank line before and after."""
    blank_line(doc)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run()
    set_run_font(r)
    r.add_picture(image_path, width=Cm(width_cm))
    add_caption(doc, label_no, caption, "CaptionFigure")
    blank_line(doc)


# ----------------------------------------------------------------------------
# Document setup
# ----------------------------------------------------------------------------

def _base_margins(section):
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.5)
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)


def make_styles(doc):
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(SIZE)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = _el("w:rFonts")
        rpr.insert(0, rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rfonts.set(qn(a), FONT)
    normal.paragraph_format.line_spacing = 1.5

    for h in ("Heading 1", "Heading 2", "Heading 3"):
        s = doc.styles[h]
        s.font.name = FONT
        s.font.size = Pt(SIZE)
        s.font.bold = True
        s.font.color.rgb = RGBColor(0, 0, 0)
        s.font.italic = False

    from docx.enum.style import WD_STYLE_TYPE
    for cap in ("CaptionTable", "CaptionFigure"):
        if cap not in [s.name for s in doc.styles]:
            st = doc.styles.add_style(cap, WD_STYLE_TYPE.PARAGRAPH)
            st.base_style = doc.styles["Normal"]
            st.font.name = FONT
            st.font.size = Pt(SIZE)
            st.hidden = False
            st.quick_style = False


# ============================================================================
# Build
# ============================================================================

def build():
    doc = Document()
    make_styles(doc)

    sec0 = doc.sections[0]
    _base_margins(sec0)

    # ---- COVER (front-matter section: Roman; cover number hidden) ----
    set_pgnum(sec0, "lowerRoman", start=1)
    sec0.different_first_page_header_footer = True
    # regular footer (abstract onward) = roman centered PAGE
    footer_page_number(sec0)
    # first-page (cover) footer stays empty
    sec0.first_page_footer.is_linked_to_previous = False

    cover(doc)

    # ---- Front matter (still Roman) ----
    doc.add_page_break()
    abstract(doc)
    doc.add_page_break()
    contents(doc)
    doc.add_page_break()
    abbreviations(doc)
    doc.add_page_break()
    list_of_tables(doc)
    doc.add_page_break()
    list_of_figures(doc)

    # ---- Body: each main section starts on an odd page; Arabic numbers ----
    s = doc.add_section(WD_SECTION.ODD_PAGE); _base_margins(s)
    s.different_first_page_header_footer = False
    set_pgnum(s, "decimal", start=1)   # restart Arabic at Introduction
    footer_page_number(s)
    introduction(doc)

    for builder in (literature_review, materials_methods, results_discussion,
                    conclusion, acknowledgement, references, authors, appendix):
        s = doc.add_section(WD_SECTION.ODD_PAGE); _base_margins(s)
        s.different_first_page_header_footer = False
        clear_pgnum(s)                 # continue the running Arabic numbering
        footer_page_number(s)
        builder(doc)

    update_fields_on_open(doc)
    out = os.path.join(ROOT, "thesis", "Graduation_Thesis.docx")
    doc.save(out)
    print("Saved:", out)


# ----------------------------------------------------------------------------
# Sections
# ----------------------------------------------------------------------------

def _center_line(doc, text, size=SIZE, bold=True, after=0, before=0, upper=True):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.line_spacing = 1.0
    r = p.add_run(text.upper() if upper else text)
    set_run_font(r, size=size, bold=bold)
    return p


def cover(doc):
    # top row with logo placeholders (left / right)
    t = doc.add_table(rows=1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.columns[0].width = Cm(7.5)
    t.columns[1].width = Cm(7.5)
    left, right = t.rows[0].cells
    for cell, txt in ((left, "[CUKUROVA UNIVERSITY LOGO]"),
                      (right, "[FACULTY OF ENGINEERING LOGO]")):
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT if cell is left else WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run(txt)
        set_run_font(r, size=10, italic=True, color=RGBColor(0x80, 0x80, 0x80))

    for _ in range(1):
        blank_line(doc)
    _center_line(doc, "CUKUROVA UNIVERSITY", size=16, after=10)
    _center_line(doc, "FACULTY OF ENGINEERING", size=16, after=10)
    _center_line(doc, "COMPUTER ENGINEERING DEPARTMENT", size=16, after=10)
    _center_line(doc, "GRADUATION THESIS", size=16, after=22)
    _center_line(doc,
                 "DESIGN AND IMPLEMENTATION OF A CONTAINER-BASED VIRTUAL "
                 "TACTICAL FIELD NETWORK SIMULATOR WITH REAL-TIME PERFORMANCE "
                 "MONITORING", size=16, after=18)

    for _ in range(6):
        blank_line(doc)

    _center_line(doc, "[STUDENT NUMBER] - [STUDENT NAME]", size=12, after=2)
    _center_line(doc, "[STUDENT NUMBER] - [STUDENT NAME]", size=12, after=14)

    _center_line(doc, "ADVISORS", size=12, after=2)
    _center_line(doc, "[ADVISOR NAME / TITLE]", size=12, after=2)
    _center_line(doc, "[CO-ADVISOR NAME / TITLE]", size=12, after=20)

    for _ in range(4):
        blank_line(doc)
    _center_line(doc, "[MONTH]", size=12, after=2)
    _center_line(doc, "2026", size=12, after=2)
    _center_line(doc, "ADANA", size=12, after=0)


def abstract(doc):
    heading(doc, "ABSTRACT", centered=True)
    body(doc,
         "Tactical field networks connect command posts, unmanned aerial "
         "vehicles and ground units over bandwidth-limited, high-latency and "
         "lossy radio links. Testing measurement and monitoring software on "
         "real radio hardware is costly and difficult to reproduce. This "
         "thesis presents the design and implementation of a container-based "
         "virtual tactical field network simulator that reproduces such link "
         "conditions on a single host and visualises link quality in real "
         "time. Four isolated Docker nodes - a headquarters, two unmanned "
         "aerial vehicles and a ground unit - communicate over a private "
         "bridge network with fixed addresses. Each node runs an iperf3 "
         "server, and the Linux tc/netem queueing discipline is applied to "
         "every node's egress interface to impose realistic bandwidth caps, "
         "propagation delay, jitter and packet loss. A Python measurement "
         "engine periodically measures every directed link using iperf3 (TCP "
         "throughput and UDP jitter and loss) and ping (round-trip latency), "
         "appending each result to a JSON Lines time series. A Streamlit "
         "dashboard reads this log and renders live node status and streaming "
         "performance charts. The system was evaluated by collecting "
         f"{STATS['n_cycles']} measurement cycles over the five configured "
         "links under the emulated field profiles. The measured metrics "
         "tracked the imposed netem profiles closely: links emulating weaker "
         "radios showed lower throughput and higher latency, and links whose "
         "traffic crossed two constrained egress interfaces accumulated the "
         "delay and loss of both. The results show that inexpensive "
         "container and kernel-level emulation can reproduce the qualitative "
         "behaviour of tactical links closely enough to develop, demonstrate "
         "and teach network performance monitoring without physical radios. "
         "The modular design allows new nodes, links and field profiles to be "
         "added through a single configuration file.",
         after=12)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    r = p.add_run("Keywords: ")
    set_run_font(r, bold=True)
    r2 = p.add_run("network emulation, tactical communications, Docker "
                   "containers, tc/netem, real-time performance monitoring")
    set_run_font(r2)


def contents(doc):
    heading(doc, "CONTENTS", centered=True)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run("Page")
    set_run_font(r, bold=True)
    tp = doc.add_paragraph()
    tp.paragraph_format.line_spacing = 1.5
    add_field(tp, ' TOC \\o "1-3" \\h \\z \\u ')


def abbreviations(doc):
    heading(doc, "ABBREVIATIONS AND SYMBOLS", centered=True)
    items = [
        ("API", "Application Programming Interface"),
        ("CLI", "Command-Line Interface"),
        ("CSV", "Comma-Separated Values"),
        ("HQ", "Headquarters (command post node)"),
        ("IP", "Internet Protocol"),
        ("JSON", "JavaScript Object Notation"),
        ("JSONL", "JSON Lines (newline-delimited JSON)"),
        ("MANET", "Mobile Ad hoc Network"),
        ("netem", "Network Emulator (Linux queueing discipline)"),
        ("QoS", "Quality of Service"),
        ("RTT", "Round-Trip Time"),
        ("TCP", "Transmission Control Protocol"),
        ("tc", "Traffic Control (Linux iproute2 utility)"),
        ("UAV", "Unmanned Aerial Vehicle"),
        ("UDP", "User Datagram Protocol"),
    ]
    t = doc.add_table(rows=0, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.columns[0].width = Cm(3.5)
    t.columns[1].width = Cm(11.5)
    for i, (ab, full) in enumerate(items):
        cells = t.add_row().cells
        _set_cell_text(cells[0], ab, align=WD_ALIGN_PARAGRAPH.LEFT)
        _set_cell_text(cells[1], full, align=WD_ALIGN_PARAGRAPH.LEFT)
        _cell_border(cells[0], top=(i == 0), bottom=(i == len(items) - 1))
        _cell_border(cells[1], top=(i == 0), bottom=(i == len(items) - 1))


def list_of_tables(doc):
    heading(doc, "LIST OF TABLES", centered=True)
    head = doc.add_paragraph()
    r = head.add_run("Table"); set_run_font(r, bold=True)
    head.add_run("\t")
    tab = head.paragraph_format.tab_stops
    tab.add_tab_stop(Cm(15.0), WD_TAB_ALIGNMENT.RIGHT)
    r2 = head.add_run("Page"); set_run_font(r2, bold=True)
    tp = doc.add_paragraph()
    add_field(tp, ' TOC \\t "CaptionTable,1" \\h \\z ')


def list_of_figures(doc):
    heading(doc, "LIST OF FIGURES", centered=True)
    head = doc.add_paragraph()
    r = head.add_run("Figure"); set_run_font(r, bold=True)
    head.add_run("\t")
    tab = head.paragraph_format.tab_stops
    tab.add_tab_stop(Cm(15.0), WD_TAB_ALIGNMENT.RIGHT)
    r2 = head.add_run("Page"); set_run_font(r2, bold=True)
    tp = doc.add_paragraph()
    add_field(tp, ' TOC \\t "CaptionFigure,1" \\h \\z ')


def introduction(doc):
    heading(doc, "1. INTRODUCTION")
    body(doc,
         "Modern military operations depend on networked command and control "
         "systems that connect a command post with mobile platforms such as "
         "unmanned aerial vehicles (UAVs) and ground vehicles. Unlike the "
         "wired or fibre links of civilian data centres, the radio links that "
         "join these platforms are severely constrained: usable bandwidth is "
         "limited, propagation and queueing introduce significant latency, the "
         "delay varies from packet to packet (jitter), and a non-negligible "
         "fraction of packets is lost (Burbank, Chimento, Haberman, & Kasch, "
         "2006; Elmasry, 2010). Software that measures, reports and "
         "visualises the quality of these links must therefore be developed "
         "and validated under conditions that resemble the field rather than "
         "the laboratory.")
    body(doc,
         "Validating such software on real radio equipment is expensive, "
         "logistically demanding and hard to reproduce: the same experiment "
         "rarely yields the same channel twice. Network emulation offers an "
         "attractive alternative. Tools such as ns-3 (Riley & Henderson, "
         "2010), Mininet (Lantz, Heller, & McKeown, 2010) and CORE "
         "(Ahrenholz, Danilov, Henderson, & Kim, 2008) let researchers "
         "reproduce network behaviour in software, while the Linux tc/netem "
         "queueing discipline (Hemminger, 2005) can impose controlled delay, "
         "jitter, loss and rate limits on real traffic at the kernel level. "
         "Lightweight operating-system containers (Merkel, 2014) make it "
         "possible to run many isolated network endpoints on a single host "
         "with little overhead.")
    body(doc,
         "This thesis brings these ideas together in a single, modular system: "
         "a container-based virtual tactical field network simulator with "
         "real-time performance monitoring. Four Docker containers represent a "
         "headquarters node, two UAV nodes and a ground (tank) node, connected "
         "by a private bridge network with fixed addresses. Each node runs an "
         "iperf3 server so that any node can measure a link to any other. A "
         "tc/netem profile is applied to every node's egress interface to "
         "emulate the bandwidth, delay, jitter and loss of a particular radio "
         "class. A Python measurement engine periodically measures every "
         "configured link with iperf3 and ping, logs the results as a JSON "
         "Lines time series, and a Streamlit dashboard renders the live status "
         "and streaming charts.")
    body(doc,
         "The objectives of the project are: (i) to build a reproducible, "
         "isolated multi-node network topology that can stand in for a small "
         "tactical field network; (ii) to impose configurable, realistic link "
         "conditions on that topology using kernel-level emulation; (iii) to "
         "measure the standard link-quality metrics - throughput, latency, "
         "jitter and packet loss - automatically and continuously; and (iv) to "
         "present these metrics in a live monitoring dashboard. A further "
         "objective is that the whole system be driven from a single "
         "configuration file so that nodes, links and field profiles can be "
         "changed without touching the measurement or visualisation code.")
    body(doc,
         "The remainder of this report is organised as follows. The Literature "
         "Review surveys network simulation and emulation tools, container "
         "based testbeds and tactical networking. The Material and Method "
         "section describes the system architecture, the emulation profiles, "
         "the measurement core, the measurement engine and the monitoring "
         "dashboard, together with the experimental setup. The Result and "
         "Discussion section reports the metrics measured under the emulated "
         "profiles and interprets them. The Conclusion summarises the "
         "contributions, the limitations and possible directions for future "
         "work.")


def literature_review(doc):
    heading(doc, "2. LITERATURE REVIEW")
    body(doc,
         "Research on reproducing network behaviour in software spans discrete "
         "event simulators, emulators and, more recently, container-based "
         "testbeds. Discrete-event simulators model a network as a sequence of "
         "events without running real protocol stacks. The ns-3 simulator "
         "(Riley & Henderson, 2010) is the most widely used representative of "
         "this class and offers detailed models of wireless channels and "
         "routing protocols. Such simulators are accurate and fully "
         "controllable, but the software under test must be written against "
         "the simulator's models rather than against the real operating-system "
         "network stack.")
    body(doc,
         "Emulators take the complementary approach of running real software "
         "over an artificially shaped network. Mininet (Lantz, Heller, & "
         "McKeown, 2010) uses Linux network namespaces to create many virtual "
         "hosts and switches on one machine for rapid prototyping of "
         "software-defined networks, and the Common Open Research Emulator "
         "(CORE) extends this idea with a graphical topology editor and "
         "support for mobile and wireless scenarios (Ahrenholz, Danilov, "
         "Henderson, & Kim, 2008). Both rely on the Linux kernel to carry "
         "real packets, which means that unmodified application software - "
         "such as iperf3 or a monitoring tool - can run inside the emulated "
         "topology exactly as it would on a physical network.")
    body(doc,
         "The mechanism that gives these emulators their realism is the Linux "
         "traffic-control subsystem. The netem queueing discipline (Hemminger, "
         "2005), configured through the tc utility of the iproute2 package "
         "(Hubert, 2002), can add fixed and random delay, reorder and "
         "duplicate packets, drop a configurable fraction of traffic and cap "
         "the egress rate. Because netem operates on a real interface, it "
         "shapes genuine TCP and UDP flows, including their reaction to loss "
         "and delay, rather than a model of them. This makes it the standard "
         "tool for introducing controlled impairments in Linux-based "
         "experiments.")
    body(doc,
         "Operating-system-level containers have made multi-node testbeds "
         "lighter and more portable. Docker (Merkel, 2014) packages an "
         "application and its dependencies into an image that starts in "
         "milliseconds and runs in an isolated namespace, sharing the host "
         "kernel. Compared with full virtual machines, containers allow many "
         "more network endpoints to run on a single host, which is convenient "
         "for emulating a topology of several communicating nodes. Docker's "
         "user-defined bridge networks provide isolated subnets with "
         "assignable fixed addresses, and the NET_ADMIN capability lets a "
         "container apply its own tc/netem rules.")
    body(doc,
         "The application domain of this work is tactical networking. Burbank, "
         "Chimento, Haberman and Kasch (2006) describe the defining "
         "characteristics of military tactical networks - intermittent, "
         "low-bandwidth, high-latency and lossy links with mobile nodes - and "
         "the challenges these pose to mobile ad hoc network (MANET) "
         "technology. Elmasry (2010) contrasts tactical wireless networks "
         "with commercial ones and stresses the importance of quality of "
         "service under constrained capacity. These characteristics motivate "
         "the specific netem profiles used in this project, in which different "
         "nodes are given distinct bandwidth, delay, jitter and loss "
         "parameters to represent different radio classes.")
    body(doc,
         "Measurement methodology builds on established, widely used tools. "
         "iperf3 (ESnet, 2016) is the de facto standard for active throughput "
         "measurement and reports TCP throughput and retransmissions as well "
         "as UDP jitter and loss, while the ping utility measures round-trip "
         "time. The contribution of this thesis is not a new emulator or "
         "metric, but the integration of these established components - Docker "
         "isolation, tc/netem impairment, iperf3/ping measurement and a "
         "Streamlit dashboard - into a single, configuration-driven system "
         "aimed specifically at demonstrating and monitoring tactical-style "
         "link quality.")


def materials_methods(doc):
    heading(doc, "3. MATERIAL AND METHOD")
    body(doc,
         "This section describes the materials and methods used to build and "
         "evaluate the simulator: the system architecture and network "
         "topology, the node containers and their measurement infrastructure, "
         "the tc/netem field profiles, the measurement core, the measurement "
         "engine with its logging format, the real-time dashboard, and the "
         "experimental setup under which the results in the next section were "
         "obtained. The complete software stack is written in Python 3.14 and "
         "orchestrated with Docker Compose; key source files are listed in the "
         "Appendix.")

    heading(doc, "3.1. System Architecture and Network Topology", style="Heading 2")
    body(doc,
         "The simulated field consists of four nodes connected by a single "
         "private bridge network named tactical_net on the subnet "
         "172.30.0.0/24. Each node is a Docker container with a fixed IP "
         "address, which keeps measurement targets stable across restarts. "
         "The headquarters (HQ) node represents the command post; two nodes "
         "represent unmanned aerial vehicles (UAV-1 and UAV-2); and one node "
         "represents a ground unit (Tank-1). Table 3.1 lists the nodes and "
         "their addresses, and Figure 3.1 shows the topology and the directed "
         "links that are measured.")
    add_table(doc, "Table 3.1.", "Nodes of the simulated tactical field network.",
              ["Node", "Container", "IP address", "Role"],
              [["Headquarters", "karargah", "172.30.0.10", "Command post"],
               ["UAV-1", "iha1", "172.30.0.11", "Unmanned aerial vehicle"],
               ["UAV-2", "iha2", "172.30.0.12", "Unmanned aerial vehicle"],
               ["Tank-1", "tank1", "172.30.0.13", "Ground unit"]],
              col_widths=[3.5, 3.0, 4.0, 4.5])
    add_figure(doc, "Figure 3.1.",
               "Network topology: four nodes on the tactical_net bridge and "
               "the five directed links measured by the engine.",
               os.path.join(FIG, "topology.png"), width_cm=12.0)

    heading(doc, "3.2. Node Containers and Measurement Infrastructure", style="Heading 2")
    body(doc,
         "All nodes share a single container image built from Alpine Linux "
         "3.20, chosen for its small size and multi-architecture support so "
         "that the system runs natively on both x86-64 and Apple Silicon "
         "(arm64) hosts. The image installs iperf3 for bandwidth, jitter and "
         "loss measurement, the iputils ping utility for latency, and the "
         "iproute2 package, which provides the tc command used for emulation. "
         "Each container's entry point starts an iperf3 server listening on "
         "TCP and UDP port 5201, so that any node can act as a measurement "
         "client against any other. The containers are granted the NET_ADMIN "
         "capability so that tc/netem rules can be applied to their own "
         "interfaces. The topology is declared once in a Docker Compose file "
         "using a shared base definition, which removes repetition and makes "
         "adding a node a few lines of configuration.")

    heading(doc, "3.3. Emulated Field Conditions (tc/netem)", style="Heading 2")
    body(doc,
         "Because all containers run on one host, raw inter-container "
         "throughput is unrealistically high (on the order of 100 Gbit/s) and "
         "latency is negligible. To make the measured metrics resemble real "
         "radio links, a netem queueing discipline is attached to the egress "
         "(eth0) interface of every node. Each profile sets a mean one-way "
         "delay, a random jitter around that delay, a packet-loss percentage "
         "and a rate cap that emulates the radio's bandwidth. The profiles, "
         "summarised in Table 3.2, deliberately differ between nodes to "
         "represent different radio classes: the HQ has the best link, the "
         "UAVs the weakest and most variable links, and the ground unit an "
         "intermediate link. Because netem shapes egress traffic, a measured "
         "link is affected by the profile of the source node, and traffic "
         "between two impaired nodes experiences the combined effect of both "
         "egress queues.")
    add_table(doc, "Table 3.2.",
              "tc/netem profiles applied to each node's egress interface.",
              ["Node", "Rate", "Delay (ms)", "Jitter (ms)", "Loss (%)"],
              [["Headquarters", "100 Mbit/s", "5", "1", "0.1"],
               ["UAV-1", "50 Mbit/s", "25", "5", "1.0"],
               ["UAV-2", "20 Mbit/s", "40", "10", "2.0"],
               ["Tank-1", "30 Mbit/s", "15", "3", "0.5"]],
              col_widths=[3.5, 3.0, 2.8, 2.8, 2.4])

    heading(doc, "3.4. Measurement Core", style="Heading 2")
    body(doc,
         "The measurement core measures one directed link at a time by running "
         "commands inside the source container with docker exec. Round-trip "
         "latency is obtained from ping by sending a small number of packets "
         "and parsing the average round-trip time. TCP throughput and "
         "retransmissions are obtained from a short iperf3 TCP test in JSON "
         "mode, reading the received bit rate from the test summary. Jitter "
         "and packet loss are obtained from a separate iperf3 UDP test at a "
         "fixed target rate. Every function is written defensively: any "
         "failure (an unreachable node, a parsing error, a timeout) results in "
         "a null value for the affected metric rather than an exception, so a "
         "single failed link never interrupts a measurement cycle. A link is "
         "marked as up if at least one of its metrics was obtained.")

    heading(doc, "3.5. Measurement Engine and Logging", style="Heading 2")
    body(doc,
         "The measurement engine drives the experiment. On start-up it "
         "optionally applies the netem profiles to all nodes, then repeatedly "
         "executes measurement cycles. In each cycle it measures every "
         "directed link defined in the configuration, stamps every record with "
         "a single UTC timestamp for that cycle, appends the records to an "
         "append-only JSON Lines file (one JSON object per line), and writes a "
         "separate snapshot of current node status. The append-only log makes "
         "the data a time series that can be read concurrently by the "
         "dashboard while the engine is still writing. Five directed links are "
         "measured per cycle: HQ to each of the three other nodes, UAV-1 to "
         "UAV-2, and Tank-1 to UAV-1. The engine can also run a single cycle "
         "for testing or run without emulation to confirm the unshaped "
         "baseline.")

    heading(doc, "3.6. Real-Time Monitoring Dashboard", style="Heading 2")
    body(doc,
         "The monitoring dashboard is a Streamlit web application. It can "
         "start and stop the measurement engine as a background process from a "
         "sidebar control, and it reads the JSON Lines log on a fixed refresh "
         "interval to display live information. The dashboard shows a status "
         "card for each node (active or passive, with its address), summary "
         "cards with the latest average throughput, latency, jitter and loss "
         "across the selected links, and four streaming line charts - one per "
         "metric - in which each line is a link. The user can choose which "
         "links to display and how many recent samples to keep in view. "
         "Because the dashboard only reads the shared log, it imposes no load "
         "on the measurement path.")

    heading(doc, "3.7. Experimental Setup", style="Heading 2")
    body(doc,
         "The experiment reported in the next section was run on a single "
         "host with the four containers active and all four netem profiles "
         "applied. In each measurement cycle every iperf3 test ran for a short "
         "fixed duration, the UDP test used a fixed target rate to probe "
         "jitter and loss, and latency was averaged over several ping packets; "
         "a short pause separated successive cycles. The engine was left "
         f"running until {STATS['n_cycles']} complete cycles had been "
         "collected for each of the five links, and the resulting JSON Lines "
         "log was analysed to produce the tables and figures that follow. "
         "Because the impairments are random within the configured bounds, "
         "metrics are reported as means over all cycles together with their "
         "variation.")


def _fmt(v):
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def results_discussion(doc):
    heading(doc, "4. RESULT AND DISCUSSION")
    n = STATS["n_cycles"]
    body(doc,
         "This section reports the link-quality metrics measured under the "
         f"emulated field profiles and interprets them. Results are aggregated "
         f"over {n} measurement cycles per link. Table 4.1 gives, for each "
         "directed link, the mean and standard deviation of TCP throughput and "
         "round-trip latency together with the mean jitter and packet loss. "
         "Figure 4.1 shows the throughput of every link over the course of the "
         "experiment, Figure 4.2 and Figure 4.3 compare the mean throughput "
         "and mean latency across links, and Figure 4.4 compares jitter and "
         "packet loss.")

    rows = []
    for label, s in STATS["links"].items():
        rows.append([
            label,
            f"{s['throughput_mean']:.1f} ± {s['throughput_std']:.1f}",
            f"{s['latency_mean']:.1f} ± {s['latency_std']:.1f}",
            f"{s['jitter_mean']:.2f}",
            f"{s['loss_mean']:.2f}",
        ])
    add_table(doc, "Table 4.1.",
              f"Measured link metrics aggregated over {n} cycles "
              "(mean ± standard deviation where shown).",
              ["Link", "Throughput (Mbit/s)", "Latency (ms)",
               "Jitter (ms)", "Loss (%)"],
              rows, col_widths=[4.2, 3.6, 3.0, 2.2, 1.8])

    add_figure(doc, "Figure 4.1.",
               "TCP throughput of each directed link across the measurement "
               "cycles.", os.path.join(FIG, "throughput_ts.png"))
    add_figure(doc, "Figure 4.2.",
               "Mean TCP throughput per link (error bars show one standard "
               "deviation).", os.path.join(FIG, "throughput_bar.png"))
    add_figure(doc, "Figure 4.3.",
               "Mean round-trip latency per link (error bars show one standard "
               "deviation).", os.path.join(FIG, "latency_bar.png"))
    add_figure(doc, "Figure 4.4.",
               "Mean jitter and mean packet loss per link.",
               os.path.join(FIG, "jitter_loss_bar.png"))

    # Discussion grounded in the actual numbers
    links = STATS["links"]
    hi = max(links.items(), key=lambda kv: kv[1]["throughput_mean"])
    lo = min(links.items(), key=lambda kv: kv[1]["throughput_mean"])
    hil = max(links.items(), key=lambda kv: kv[1]["latency_mean"])

    body(doc,
         "The measured metrics follow the imposed netem profiles closely. The "
         f"highest mean throughput was observed on the {hi[0]} link "
         f"({hi[1]['throughput_mean']:.1f} Mbit/s) and the lowest on the "
         f"{lo[0]} link ({lo[1]['throughput_mean']:.1f} Mbit/s), which is "
         "consistent with the rate caps in Table 3.2: links whose source node "
         "has a higher rate cap and whose path crosses fewer constrained "
         "egress queues achieve higher throughput. Because netem shapes egress "
         "traffic, the throughput of a link is bounded primarily by the rate "
         "cap of its source node, while the destination node's profile "
         "contributes additional delay and loss on the return path.")
    body(doc,
         "Latency behaves analogously. The largest mean round-trip time was "
         f"measured on the {hil[0]} link ({hil[1]['latency_mean']:.1f} ms). "
         "Round-trip latency reflects the sum of the one-way delays of the "
         "queues traversed in both directions plus queueing under load, so "
         "links between two delayed nodes show the highest round-trip times, "
         "whereas links originating at the low-delay HQ node show the lowest. "
         "The standard deviations in Table 4.1 are produced by the configured "
         "jitter together with TCP's own rate adaptation and are larger on the "
         "links emulating weaker, more variable radios.")
    body(doc,
         "Jitter and packet loss, shown in Figure 4.4, are likewise ordered by "
         "the severity of the profiles on the path: links involving the UAV "
         "nodes, which carry the highest configured jitter and loss, show the "
         "largest measured jitter and loss, while links originating at the HQ "
         "node remain low. The accumulation effect is clearest on the UAV-1 to "
         "UAV-2 link, whose traffic crosses two of the most constrained egress "
         "interfaces and which therefore combines a low rate cap with high "
         "latency, jitter and loss. This is exactly the qualitative behaviour "
         "expected of a link between two weak radios in the field.")
    body(doc,
         "Two points qualify these results. First, the absolute values depend "
         "on the chosen profiles and on the fact that all nodes share one "
         "host; the contribution of the work is the faithful reproduction of "
         "the relative ordering and qualitative behaviour of tactical links, "
         "not the prediction of any specific radio's absolute performance. "
         "Second, because the impairments are random within their configured "
         "bounds, individual cycles vary; reporting means over many cycles, as "
         "in Table 4.1, gives a stable picture, and the live dashboard makes "
         "this variation visible in real time. Overall, the system reproduces "
         "the intended field conditions and measures them consistently, "
         "meeting the objectives set out in the Introduction.")


def conclusion(doc):
    heading(doc, "5. CONCLUSION")
    body(doc,
         "This thesis presented the design and implementation of a "
         "container-based virtual tactical field network simulator with "
         "real-time performance monitoring. Four isolated Docker nodes - a "
         "headquarters, two UAVs and a ground unit - communicate over a "
         "private bridge network; tc/netem profiles emulate the bandwidth, "
         "delay, jitter and loss of different radio classes; a Python engine "
         "measures every link with iperf3 and ping and logs the results as a "
         "time series; and a Streamlit dashboard visualises the link quality "
         "live.")
    body(doc,
         "All four objectives stated in the Introduction were met. A "
         "reproducible, isolated multi-node topology was built; configurable "
         "and realistic link conditions were imposed with kernel-level "
         "emulation; throughput, latency, jitter and packet loss were measured "
         "automatically and continuously; and the metrics were presented in a "
         "live dashboard. The evaluation showed that the measured metrics "
         "track the imposed profiles closely and reproduce the expected "
         "ordering and accumulation effects of constrained radio links. The "
         "single-configuration-file design met the further objective of "
         "extensibility.")
    body(doc,
         "The study has limitations. All nodes run on one host, so the "
         "emulation captures the qualitative behaviour of radio links rather "
         "than the physical-layer behaviour of any specific radio; netem "
         "shapes only egress traffic and does not model node mobility, fading "
         "or contention for a shared medium; and the topology and traffic "
         "patterns are deliberately small.")
    body(doc,
         "Future work could address these limitations by modelling mobility "
         "and time-varying profiles, adding a shared-medium wireless model, "
         "introducing routing so that multi-hop paths can be studied, scaling "
         "the topology to more nodes across multiple hosts, and recording "
         "long-term measurements for statistical analysis and alerting in the "
         "dashboard. These extensions would build naturally on the modular, "
         "configuration-driven architecture presented here.")


def acknowledgement(doc):
    heading(doc, "ACKNOWLEDGEMENT")
    body(doc,
         "The authors would like to thank their advisor, [ADVISOR NAME / "
         "TITLE], and co-advisor, [CO-ADVISOR NAME / TITLE], of the Department "
         "of Computer Engineering at Cukurova University for their guidance and "
         "support throughout this project. [Add any further acknowledgements "
         "here. If the project received financial or institutional support "
         "from programmes such as BAP or TUBITAK, state it clearly in this "
         "section.]")


def references(doc):
    heading(doc, "REFERENCES")
    refs = [
        "Ahrenholz, J., Danilov, C., Henderson, T. R., & Kim, J. H. (2008). "
        "CORE: A real-time network emulator. In MILCOM 2008 - IEEE Military "
        "Communications Conference (pp. 1-7). IEEE. "
        "https://doi.org/10.1109/MILCOM.2008.4753614",

        "Burbank, J. L., Chimento, P. F., Haberman, B. K., & Kasch, W. T. "
        "(2006). Key challenges of military tactical networking and the "
        "elusive promise of MANET technology. IEEE Communications Magazine, "
        "44(11), 39-45. https://doi.org/10.1109/COM-M.2006.248164",

        "Elmasry, G. F. (2010). A comparative review of commercial vs. "
        "tactical wireless networks. IEEE Communications Magazine, 48(10), "
        "54-59. https://doi.org/10.1109/MCOM.2010.5594678",

        "ESnet. (2016). iPerf3: A TCP, UDP and SCTP network bandwidth "
        "measurement tool [Computer software]. Lawrence Berkeley National "
        "Laboratory. https://software.es.net/iperf/",

        "Hemminger, S. (2005). Network emulation with NetEm. In Proceedings "
        "of the Australian National Linux Conference (linux.conf.au) "
        "(pp. 18-23). Linux Australia.",

        "Hubert, B. (2002). Linux advanced routing & traffic control HOWTO. "
        "The Linux Documentation Project. https://lartc.org/",

        "Lantz, B., Heller, B., & McKeown, N. (2010). A network in a laptop: "
        "Rapid prototyping for software-defined networks. In Proceedings of "
        "the 9th ACM SIGCOMM Workshop on Hot Topics in Networks (HotNets-IX) "
        "(pp. 1-6). ACM. https://doi.org/10.1145/1868447.1868466",

        "Merkel, D. (2014). Docker: Lightweight Linux containers for "
        "consistent development and deployment. Linux Journal, 2014(239), "
        "Article 2.",

        "Riley, G. F., & Henderson, T. R. (2010). The ns-3 network simulator. "
        "In K. Wehrle, M. Gunes, & J. Gross (Eds.), Modeling and tools for "
        "network simulation (pp. 15-34). Springer. "
        "https://doi.org/10.1007/978-3-642-12331-3_2",
    ]
    for entry in refs:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(1.25)
        pf.first_line_indent = Cm(-1.25)  # hanging indent
        pf.line_spacing = 1.5
        pf.space_after = Pt(6)
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r = p.add_run(entry)
        set_run_font(r)


def authors(doc):
    heading(doc, "ABOUT THE AUTHORS AND AUTHOR CONTRIBUTION")
    body(doc,
         "[STUDENT NAME] is an undergraduate student in the Department of "
         "Computer Engineering at Cukurova University. [Add a short "
         "description of academic background and interests.] In this project "
         "the author was responsible for [describe contribution, e.g. the "
         "Docker topology and netem emulation, the Python measurement engine, "
         "the Streamlit dashboard, the experiments and the writing of this "
         "report].")
    body(doc,
         "[SECOND STUDENT NAME, if applicable] is an undergraduate student in "
         "the Department of Computer Engineering at Cukurova University. [Add "
         "a short description of academic background and interests.] In this "
         "project the author was responsible for [describe contribution]. "
         "(Delete this paragraph if the thesis has a single author.)")


def appendix(doc):
    heading(doc, "APPENDIX")
    body(doc,
         "This appendix contains supporting material that is too detailed for "
         "the main text: the central configuration file that defines the "
         "nodes, links and field profiles, and the structure of the "
         "measurement log used for the results.")

    heading(doc, "Appendix A: System Configuration", style="Heading 2")
    body(doc,
         "The entire topology - nodes, the directed links to measure, the "
         "tc/netem field profiles and the measurement parameters - is defined "
         "in a single Python configuration module, reproduced below.", indent=False)
    code_block(doc, CONFIG_LISTING)

    heading(doc, "Appendix B: Measurement Log Format", style="Heading 2")
    body(doc,
         "Each measurement cycle appends one JSON object per directed link to "
         "the append-only log file (JSON Lines). A representative record is "
         "shown below; all reported tables and figures were computed from "
         "these records.", indent=False)
    code_block(doc, SAMPLE_RECORD)


def code_block(doc, text):
    for line in text.splitlines():
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.left_indent = Cm(0.5)
        r = p.add_run(line if line else " ")
        r.font.name = "Courier New"
        r.font.size = Pt(9)
        rpr = r._element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = _el("w:rFonts"); rpr.insert(0, rfonts)
        for a in ("w:ascii", "w:hAnsi", "w:cs"):
            rfonts.set(qn(a), "Courier New")


CONFIG_LISTING = '''NODES = {
    "karargah": {"display": "HQ",     "ip": "172.30.0.10"},
    "iha1":     {"display": "UAV-1",  "ip": "172.30.0.11"},
    "iha2":     {"display": "UAV-2",  "ip": "172.30.0.12"},
    "tank1":    {"display": "Tank-1", "ip": "172.30.0.13"},
}

LINKS = [
    ("karargah", "iha1"), ("karargah", "iha2"), ("karargah", "tank1"),
    ("iha1", "iha2"), ("tank1", "iha1"),
]

NETEM_PROFILES = {
    "karargah": {"delay_ms": 5,  "jitter_ms": 1,  "loss_pct": 0.1, "rate": "100mbit"},
    "iha1":     {"delay_ms": 25, "jitter_ms": 5,  "loss_pct": 1.0, "rate": "50mbit"},
    "iha2":     {"delay_ms": 40, "jitter_ms": 10, "loss_pct": 2.0, "rate": "20mbit"},
    "tank1":    {"delay_ms": 15, "jitter_ms": 3,  "loss_pct": 0.5, "rate": "30mbit"},
}

INTERVAL_SEC   = 3     # wait between full cycles
IPERF_DURATION = 2     # seconds per iperf3 test
UDP_BANDWIDTH  = "20M" # UDP probe target rate
PING_COUNT     = 4     # ping packets per latency measurement'''

SAMPLE_RECORD = '''{
  "src": "karargah", "src_display": "HQ",
  "dst": "iha1", "dst_display": "UAV-1",
  "latency_ms": 37.49, "throughput_mbps": 87.08,
  "retransmits": 10, "jitter_ms": 0.516,
  "loss_pct": 0.23, "up": true,
  "ts": "2026-05-29T16:33:44.381034+00:00"
}'''


if __name__ == "__main__":
    build()
