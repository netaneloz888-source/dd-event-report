from datetime import datetime
import io
import os
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from bidi.algorithm import get_display
from PIL import Image, ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
import streamlit as st

st.set_page_config(
    page_title="ד.ד. מהנדסים בע''מ - תחקור אירוע בצומת",
    page_icon="🚦",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        direction: rtl;
        text-align: right;
    }
    input, textarea, select {
        direction: rtl;
        text-align: right;
    }
    div[data-testid="stFileUploader"] {
        direction: rtl;
    }
    div[data-baseweb="select"] > div {
        direction: rtl;
        text-align: right;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).resolve().parent
ALEF_URL = "https://github.com/google/fonts/raw/main/ofl/alef/"


def heb(text):
    if not text:
        return ""
    lines = str(text).split("\n")
    return "<br/>".join(escape(get_display(line)) for line in lines)


def _find_or_download(filename):
    for folder in (BASE_DIR, Path.cwd()):
        p = folder / filename
        if p.exists():
            return str(p)
    try:
        target = BASE_DIR / filename
        urllib.request.urlretrieve(ALEF_URL + filename, target)
        return str(target)
    except Exception:
        return None


def register_fonts():
    reg = _find_or_download("Alef-Regular.ttf")
    bold = _find_or_download("Alef-Bold.ttf")
    if reg and bold:
        try:
            pdfmetrics.registerFont(TTFont("AlefRegular", reg))
            pdfmetrics.registerFont(TTFont("AlefBold", bold))
            return "AlefRegular", "AlefBold"
        except Exception as e:
            print("Error registering Alef:", e)

    dejavu = "/usr/share/fonts/truetype/dejavu/"
    if os.path.exists(dejavu + "DejaVuSans.ttf"):
        pdfmetrics.registerFont(TTFont("DejaVu", dejavu + "DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont("DejaVuBold", dejavu + "DejaVuSans-Bold.ttf"))
        return "DejaVu", "DejaVuBold"

    st.error("לא נמצא פונט עברי. העלה את Alef-Regular.ttf ו-Alef-Bold.ttf לתיקיית הפרויקט.")
    return "Helvetica", "Helvetica-Bold"


def build_investigation_pdf(event_data, inspector_data, items):
    font_reg, font_bold = register_fonts()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
        title=f"דוח תחקיר אירוע - {event_data['junction_name']}",
    )

    story = []

    # סגנונות טקסט
    title_style = ParagraphStyle(
        "TitleStyle",
        fontName=font_bold,
        fontSize=15,
        leading=20,
        textColor=colors.HexColor("#124E91"),
        alignment=2,
    )
    sub_title_style = ParagraphStyle(
        "SubTitleStyle",
        fontName=font_bold,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#9B1C1C"),  # אדום כהה להדגשת אירוע
        alignment=2,
    )
    section_header_style = ParagraphStyle(
        "SectionHeader",
        fontName=font_bold,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#124E91"),
        alignment=2,
    )
    body_style = ParagraphStyle(
        "BodyStyle",
        fontName=font_reg,
        fontSize=10,
        leading=14.5,
        textColor=colors.HexColor("#1A1A1A"),
        alignment=2,
    )
    table_label_style = ParagraphStyle(
        "TableLabel",
        fontName=font_bold,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#124E91"),
        alignment=2,
    )
    table_val_style = ParagraphStyle(
        "TableVal",
        fontName=font_reg,
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#1A1A1A"),
        alignment=2,
    )

    # כותרת עליונה ולוגו
    header_title = heb("ד.ד. מהנדסים בע''מ - דוח תחקור אירוע בצומת")
    event_num_display = event_data["event_id"] or "ללא מספר"
    header_sub = heb(
        f"מס' אירוע: {event_num_display}  |  צומת: {event_data['junction_name'] or 'לא צוין'}  |  תאריך הפקת דוח: {event_data['report_date']}"
    )

    text_block = [
        Paragraph(header_title, title_style),
        Spacer(1, 2 * mm),
        Paragraph(header_sub, sub_title_style),
    ]

    if os.path.exists("logo.png"):
        try:
            logo_img = RLImage("logo.png", width=36 * mm, height=16 * mm, kind="proportional")
            top_table = Table([[logo_img, text_block]], colWidths=[42 * mm, 140 * mm])
            top_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (0, 0), "LEFT"),
                        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ]
                )
            )
            story.append(top_table)
        except Exception:
            story.extend(text_block)
    else:
        story.extend(text_block)

    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width="100%", thickness=1.4, color=colors.HexColor("#124E91")))
    story.append(Spacer(1, 4 * mm))

    # טבלת תעודת זהות לאירוע (מימין לשמאל בעמודות)
    meta_rows = [
        [
            Paragraph(heb(event_data["event_datetime"]), table_val_style),
            Paragraph(heb("מועד האירוע:"), table_label_style),
            Paragraph(heb(event_data["junction_name"] or "-"), table_val_style),
            Paragraph(heb("שם / מס' צומת:"), table_label_style),
        ],
        [
            Paragraph(heb(event_data["event_type"]), table_val_style),
            Paragraph(heb("סיווג אירוע:"), table_label_style),
            Paragraph(heb(event_data["event_id"] or "-"), table_val_style),
            Paragraph(heb("מספר אירוע / קריאה:"), table_label_style),
        ],
        [
            Paragraph(heb(event_data["contractor_status"]), table_val_style),
            Paragraph(heb("סטטוס טיפול:"), table_label_style),
            Paragraph(heb(event_data["reporter"] or "-"), table_val_style),
            Paragraph(heb("גורם מדווח / מזמין:"), table_label_style),
        ],
    ]

    meta_table = Table(meta_rows, colWidths=[56 * mm, 35 * mm, 56 * mm, 35 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7FB")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#9BB2CE")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0DCEB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    # פונקציית עזר לבלוק מלל מעוצב
    def add_text_section(title_txt, content_txt, border_color="#B8C6D8", bg_color="#FFFFFF"):
        if not content_txt or not content_txt.strip():
            return
        sec_table = Table(
            [
                [Paragraph(heb(title_txt), section_header_style)],
                [Paragraph(heb(content_txt.strip()), body_style)],
            ],
            colWidths=[182 * mm],
        )
        sec_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor(border_color)),
                    ("LINEBELOW", (0, 0), (0, 0), 0.5, colors.HexColor("#E2E8F0")),
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#EEF3F9")),
                    ("BACKGROUND", (0, 1), (0, 1), colors.HexColor(bg_color)),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(sec_table)
        story.append(Spacer(1, 4 * mm))

    # סעיפי התחקיר
    add_text_section("1. תיאור האירוע וממצאים בשטח", event_data["description"])
    add_text_section("2. פעולות שננקטו לטיפול מיידי / השבתת תקלה", event_data["actions_taken"])
    add_text_section("3. מסקנות התחקיר והנחיות להמשך", event_data["conclusions"])

    # נספח תמונות (אם הועלו)
    if items:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(heb("4. תיעוד מצולם מהשטח"), section_header_style))
        story.append(Spacer(1, 3 * mm))

        for idx, item in enumerate(items, start=1):
            img = Image.open(item["file"])
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            img_io = io.BytesIO()
            img.save(img_io, format="JPEG", quality=85)
            img_io.seek(0)

            img_reader = ImageReader(img_io)
            iw, ih = img_reader.getSize()
            max_w = 68 * mm
            max_h = 48 * mm
            scale = min(max_w / max(iw, 1), max_h / max(ih, 1))
            rl_img = RLImage(img_io, width=iw * scale, height=ih * scale)

            desc_raw = item["desc"].strip() if item["desc"] and item["desc"].strip() else "ללא תיאור נוסף."
            right_cell = [
                Paragraph(heb(f"ממצא מצולם {idx}"), section_header_style),
                Spacer(1, 2 * mm),
                Paragraph(heb(desc_raw), body_style),
            ]

            row_table = Table([[right_cell, rl_img]], colWidths=[108 * mm, 74 * mm])
            row_table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#B8C6D8")),
                        ("LINEBEFORE", (1, 0), (1, -1), 0.7, colors.HexColor("#B8C6D8")),
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCFDFE")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (0, 0), (0, 0), "RIGHT"),
                        ("ALIGN", (1, 0), (1, 0), "CENTER"),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(row_table)
            story.append(Spacer(1, 4 * mm))

    # חתימת מפקח בתחתית הדוח
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#124E91")))
    story.append(Spacer(1, 3 * mm))

    inspector_line = heb("כל הזכויות שייכות לנתנאל עוז הררי 0545520445")
    sig_table = Table([[Paragraph(inspector_line, table_val_style)]], colWidths=[182 * mm])
    sig_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF3F9")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#9BB2CE")),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(sig_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ================= ממשק המשתמש =================
col_logo, col_title = st.columns([1, 4])
with col_logo:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
with col_title:
    st.title("ד.ד. מהנדסים בע''מ")
    st.caption("מערכת תחקור אירועים ותקלות בצמתי רמזורים")

st.divider()

# חלק 1: פרטי אירוע וצומת
st.subheader("1. פרטי האירוע והצומת")
r1_c1, r1_c2, r1_c3 = st.columns(3)
with r1_c1:
    junction_name = st.text_input("שם צומת / מס' צומת *", placeholder="לדוגמה: צומת כנות / 402")
with r1_c2:
    event_id = st.text_input("מספר אירוע / קריאת מוקד", placeholder="לדוגמה: 2026-8841")
with r1_c3:
    event_type = st.selectbox(
        "סיווג האירוע",
        [
            "תקלת בקר / מערכת רמזורים",
            "תאונת דרכים / פגיעה בעמוד או תשתית",
            "הפסקת חשמל / הזנת חברת חשמל",
            "חריגה בהסדרי תנועה / בטיחות",
            "אחר",
        ],
    )

r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
with r2_c1:
    event_date = st.date_input("תאריך האירוע", value=datetime.now())
with r2_c2:
    event_time = st.time_input("שעת האירוע", value=datetime.now().time())
with r2_c3:
    reporter = st.text_input("גורם מדווח / מזמין", placeholder="לדוגמה: מוקד נתיבי ישראל / משטרה")
with r2_c4:
    contractor_status = st.selectbox(
        "סטטוס טיפול נוכחי",
        [
            "טופל והוחזר לשגרה",
            "בטיפול קבלן אחזקה / הקמה",
            "הועבר להבהוב צהוב / מנותק",
            "ממתין לאישור / חלקי חילוף",
        ],
    )

st.divider()

# חלק 2: מלל התחקיר
st.subheader("2. פרטי התחקיר וממצאים")
description = st.text_area(
    "תיאור האירוע והממצאים בשטח *",
    height=140,
    placeholder="פרט מה אירע בצומת, מצב הרמזורים עם ההגעה לשטח, נזקים לתשתית/בקר/כבלים, וכל ממצא רלוונטי...",
)

c_act, c_conc = st.columns(2)
with c_act:
    actions_taken = st.text_area(
        "פעולות שבוצעו לטיפול מיידי",
        height=110,
        placeholder="לדוגמה: בידוד כבל פגוע, איפוס בקר, תיאום מול קבלן אחזקה, הכוונת תנועה...",
    )
with c_conc:
    conclusions = st.text_area(
        "מסקנות התחקיר והנחיות להמשך",
        height=110,
        placeholder="לדוגמה: נדרש שיקום עמוד פגוע תוך 48 שעות, בדיקת הארקה והגשת דוח נזק...",
    )

st.divider()

# חלק 3: תמונות (אופציונלי)
st.subheader("3. תיעוד מצולם (אופציונלי)")
uploaded_files = st.file_uploader(
    "העלה או צלם תמונות מהאירוע (ניתן להפיק דוח גם ללא תמונות)",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

items_data = []
if uploaded_files:
    for i, file in enumerate(uploaded_files):
        with st.container():
            col_img, col_desc = st.columns([1, 2])
            with col_img:
                st.image(file, use_container_width=True)
            with col_desc:
                desc = st.text_area(
                    f"תיאור תמונה {i + 1}",
                    key=f"desc_{i}",
                    height=130,
                    placeholder="הסבר מה רואים בתמונה (לדוגמה: פגיעה ברגל עמוד 3, כבל חשוף בבור תקשורת)...",
                )
                items_data.append({"file": file, "desc": desc})

st.divider()

# חלק 4: פרטי עורך התחקיר
st.subheader("4. פרטי עורך התחקיר")
i1, i2, i3, i4 = st.columns(4)
with i1:
    inspector_name = st.text_input("שם המפקח", value="נתנאל עוז הררי")
with i2:
    license_type = st.text_input("סוג רישיון", value="הנדסאי חשמל / מפקח הסדרי תנועה")
with i3:
    license_num = st.text_input("מס' רישיון", placeholder="הזן מס' רישיון")
with i4:
    phone = st.text_input("טלפון", value="054-5520445")

st.divider()

if "inv_pdf_bytes" not in st.session_state:
    st.session_state.inv_pdf_bytes = None
    st.session_state.inv_pdf_name = None

if st.button("📋 הפק דוח תחקיר PDF", type="primary", use_container_width=True):
    if not junction_name.strip() or not description.strip():
        st.warning("נא למלא לפחות את שם הצומת ואת תיאור האירוע לפני הפקת הדוח.")
    else:
        with st.spinner("מייצר דוח תחקיר PDF..."):
            event_info = {
                "junction_name": junction_name.strip(),
                "event_id": event_id.strip(),
                "event_type": event_type,
                "event_datetime": f"{event_date.strftime('%d/%m/%Y')} בשעה {event_time.strftime('%H:%M')}",
                "reporter": reporter.strip(),
                "contractor_status": contractor_status,
                "description": description,
                "actions_taken": actions_taken,
                "conclusions": conclusions,
                "report_date": datetime.now().strftime("%d/%m/%Y"),
            }
            inspector_info = {
                "name": inspector_name,
                "license_type": license_type,
                "license_num": license_num,
                "phone": phone,
            }
            pdf_bytes = build_investigation_pdf(
                event_data=event_info,
                inspector_data=inspector_info,
                items=items_data,
            )
            clean_junction = junction_name.strip().replace(" ", "_")
            clean_event = f"_{event_id.strip().replace(' ', '_')}" if event_id.strip() else ""
            st.session_state.inv_pdf_bytes = pdf_bytes
            st.session_state.inv_pdf_name = f"תחקיר_{clean_junction}{clean_event}_{datetime.now().strftime('%Y%m%d')}.pdf"

if st.session_state.inv_pdf_bytes:
    st.success("דוח התחקיר מוכן להורדה!")
    st.download_button(
        label="⬇️ הורד דוח תחקיר PDF",
        data=st.session_state.inv_pdf_bytes,
        file_name=st.session_state.inv_pdf_name,
        mime="application/pdf",
        use_container_width=True,
    )
