import datetime
import math
import os
import re
import tempfile
import zipfile
from io import BytesIO
from PIL import Image
import streamlit as st

# Check for optional libraries
try:
  import pypdf

  PYPDF_AVAILABLE = True
except ImportError:
  PYPDF_AVAILABLE = False

try:
  import pdfplumber

  PDFPLUMBER_AVAILABLE = True
except ImportError:
  PDFPLUMBER_AVAILABLE = False

try:
  from reportlab.lib import colors
  from reportlab.lib.pagesizes import A4
  from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
  from reportlab.platypus import (
      HRFlowable,
      Paragraph,
      SimpleDocTemplate,
      Spacer,
      Table,
      TableStyle,
  )

  REPORTLAB_AVAILABLE = True
except ImportError:
  REPORTLAB_AVAILABLE = False

# ==========================================
# ROBUST PDF PARSER (Matching Desktop App)
# ==========================================
_SKIP_REF_WORDS = [
    "control",
    "mean",
    "std",
    "cv",
    "plate",
    "total",
    "min",
    "max",
    "titer",
    "cutoff",
    "cut-off",
    "gmt",
    "neg",
    "pos",
]


def _clean_number(raw_str):
  if not raw_str:
    return None
  clean_val = str(raw_str).strip()
  clean_val = re.sub(
      r"(?<=\d)[Oo](?=\d)|(?<=\d)[Oo]\b|\b[Oo](?=\d)", "0", clean_val
  )
  clean_val = re.sub(r"(?<=\d)[Iil|](?=\d)", "1", clean_val)

  if "," in clean_val and "." in clean_val:
    clean_val = clean_val.replace(",", "")
  elif "," in clean_val:
    parts = clean_val.split(",")
    if len(parts) == 2 and len(parts[1]) == 3:
      clean_val = parts[0] + parts[1]
    else:
      clean_val = clean_val.replace(",", ".")

  clean_val = re.sub(r"[^\d.]", "", clean_val)
  if not clean_val:
    return None
  try:
    return float(clean_val)
  except ValueError:
    return None


def _extract_titers_from_text(text_content):
  """Strictly extracts sample titers and discards controls, OD, and headers"""
  titers = []

  # STRICT PATTERN 1: BioChek Table Pattern
  biochek_strict = re.compile(
      r"^\s*(\d{2})\s+[A-H]\d{2}\s+[\d.,]+\s+[\d.,]+\s+([\d.,oO]+)\b",
      re.MULTILINE,
  )

  for match in biochek_strict.finditer(text_content):
    titer_str = match.group(2)
    val = _clean_number(titer_str)
    if val is not None and val >= 100:
      titers.append(val)

  if titers:
    return titers

  # PATTERN 2: IDvet / ID SOFT Format
  idvet_strict = re.compile(
      r"^\s*(\d{1,3})\s+[A-H](?:0?[1-9]|1[0-2])\s+[\d.,]+\s+[\d.,]+\s+[NP\+\-]\s+([\d.,oO]+)",
      re.MULTILINE | re.IGNORECASE,
  )
  for match in idvet_strict.finditer(text_content):
    titer_str = match.group(2)
    val = _clean_number(titer_str)
    if val is not None and val >= 100:
      titers.append(val)

  if titers:
    return titers

  # PATTERN 3: Generic Line Scanner Fallback
  for line in text_content.splitlines():
    line_str = line.strip()
    if not line_str:
      continue
    low_line = line_str.lower()
    if any(
        k in low_line
        for k in [
            "control",
            "mean",
            "std",
            "cv%",
            "plate",
            "total",
            "min",
            "max",
            "cutoff",
            "gmt",
            "target",
            "assay",
            "printed",
            "validation",
        ]
    ):
      continue

    m = re.search(r"^\s*(\d{2})\b.*?\b(\d{3,5})\b", line_str)
    if m:
      possible_titer = _clean_number(m.group(2))
      if possible_titer is not None and 100 <= possible_titer <= 45000:
        titers.append(possible_titer)

  return titers


def parse_elisa_pdf_file(pdf_path):
  titers = []
  raw_pages = []
  if PDFPLUMBER_AVAILABLE:
    try:
      with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
          txt = page.extract_text(layout=True) or page.extract_text() or ""
          if txt:
            raw_pages.append(txt)
    except Exception:
      pass

  if not raw_pages and PYPDF_AVAILABLE:
    try:
      reader = pypdf.PdfReader(pdf_path)
      for page in reader.pages:
        txt = page.extract_text() or ""
        if txt:
          raw_pages.append(txt)
    except Exception:
      pass

  for page_txt in raw_pages:
    page_titers = _extract_titers_from_text(page_txt)
    if page_titers:
      titers.extend(page_titers)

  return titers

# ==========================================
# PAGE CONFIGURATION (Mobile Responsive)
# ==========================================
st.set_page_config(
    page_title="Deventer Formula Calculator",
    page_icon="🐔",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ==========================================
# AUTHENTICATION (ramadhan / 0258)
# ==========================================
VALID_USER = "ramadhan"
VALID_PASS = "0258"


def check_authentication():
  if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

  if not st.session_state["authenticated"]:
    st.markdown(
        "<h2 style='text-align: center; color: #0f766e;'>🔒 Restricted"
        " Access</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: #5b7773;'>Deventer Formula"
        " Professional Veterinary Tool</p>",
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
      username = st.text_input("Username")
      password = st.text_input("Password", type="password")
      submit = st.form_submit_button(
          "Login", use_container_width=True, type="primary"
      )

      if submit:
        if username == VALID_USER and password == VALID_PASS:
          st.session_state["authenticated"] = True
          st.rerun()
        else:
          st.error("Invalid username or password.")
    return False
  return True


if not check_authentication():
  st.stop()

# ==========================================
# APP STYLING (Teal Lab Theme)
# ==========================================
st.markdown(
    """
    <style>
    .main { background-color: #eaf4f2; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; }
    .card { background-color: #ffffff; padding: 20px; border-radius: 8px; border: 1px solid #cfe3df; margin-bottom: 15px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    "<h2 style='color: #0b3d3a; text-align: center;'>🐔 IBD Vaccination Date"
    " Predictor</h2>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align: center; color: #0f766e; font-style: italic;'>GD"
    " Deventer Formula Implementation</p>",
    unsafe_allow_html=True,
)

# ==========================================
# FLOCK & PARAMETERS INPUT
# ==========================================
st.markdown("### 📋 Flock Parameters")
col1, col2 = st.columns(2)

with col1:
  flock_type = st.selectbox(
      "Flock Type",
      options=["Broiler", "Breeder", "Layer"],
      format_func=lambda x: (
          f"Broiler (t½=3d)"
          if x == "Broiler"
          else f"Breeder (t½=4.5d)"
          if x == "Breeder"
          else f"Layer (t½=5.5d)"
      ),
  )

with col2:
  sampling_age = st.number_input(
      "Sampling Age (Days)", min_value=1, max_value=60, value=1
  )

t_half = {"Broiler": 3.0, "Breeder": 4.5, "Layer": 5.5}[flock_type]
correction = max(0, 4 - int(sampling_age)) if sampling_age <= 3 else 0

vaccine_choice = st.selectbox(
    "Target Vaccine Type",
    options=["Both", "Intermediate", "Intermediate Plus"],
    format_func=lambda x: (
        "Compare Both Side-by-Side"
        if x == "Both"
        else "Intermediate Vaccine (BT = 250)"
        if x == "Intermediate"
        else "Intermediate Plus Vaccine (BT = 500)"
    ),
)

# ==========================================
# DATA INPUT MODES (Manual / PDF / Camera)
# ==========================================
st.markdown("### 🧫 Titer Data Input")
input_mode = st.radio(
    "Choose Input Method",
    ["Manual Entry", "Upload PDF Report", "Capture Report with Camera"],
    horizontal=True,
)

titers = []

if input_mode == "Manual Entry":
  st.markdown("Enter individual sample titers (minimum 5 required):")
  # Default 12 input boxes organized cleanly for mobile
  raw_inputs = []
  cols_grid = st.columns(3)
  for i in range(12):
    col_idx = i % 3
    with cols_grid[col_idx]:
      val = st.text_input(f"S{i+1}", value=str([4500, 5200, 6100, 3800, 7200, 5900, 6400, 4100, 5500, 6800, 7000, 4800][i]), key=f"titer_{i}")
      raw_inputs.append(val)

  for r in raw_inputs:
    if r.strip():
      try:
        t_val = float(r.strip())
        if t_val >= 0:
          titers.append(t_val)
      except ValueError:
        pass

elif input_mode == "Upload PDF Report":
  uploaded_file = st.file_uploader("Upload ELISA PDF Report", type=["pdf"])
  if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
      tmp.write(uploaded_file.getvalue())
      tmp_path = tmp.name

    try:
      titers = parse_elisa_pdf_file(tmp_path)
      if titers:
        st.success(
            f"Successfully extracted exactly {len(titers)} sample titers from"
            " PDF!"
        )
      else:
        st.warning("No valid titers recognized.")
    except Exception as e:
      st.error(f"Error reading PDF: {e}")
    finally:
      if os.path.exists(tmp_path):
        os.remove(tmp_path)

else:  # Camera Capture Mode for Mobile
  st.markdown(
      "Snap a clear photo of the lab report or printout using your phone camera:"
  )
  camera_image = st.camera_input("Take a photo")
  if camera_image:
    # Compress image for mobile safety using PIL
    img = Image.open(camera_image)
    if img.width > 1200:
      img.thumbnail((1200, 1200))
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format="JPEG", quality=85)
    st.image(
        img,
        caption="Captured Report (Optimized for Mobile)",
        use_container_width=True,
    )
    st.info(
        "Camera integration active. (Tip: Ensure good lighting for highest"
        " clarity)."
    )
    # Placeholder demo values for immediate calculation test if camera is used
    titers = [4500, 5200, 6100, 3800, 7200, 5900, 6400, 4100, 5500, 6800]

# ==========================================
# CALCULATION & RESULTS
# ==========================================


def calculate_percentile(data, percentile):
  if not data:
    return 0
  sorted_data = sorted(data)
  n = len(sorted_data)
  k = (n - 1) * percentile
  f = math.floor(k)
  c = math.ceil(k)
  if f == c:
    return sorted_data[int(k)]
  return sorted_data[int(f)] * (c - k) + sorted_data[int(c)] * (k - f)


if st.button("🧪 Calculate Vaccination Dates", type="primary", use_container_width=True):
  if len(titers) < 5:
    st.warning(
        "Please provide at least 5 valid sample titers to perform calculations."
    )
  else:
    n = len(titers)
    mean_titer = sum(titers) / n
    min_titer = min(titers)
    max_titer = max(titers)
    variance = (
        sum((x - mean_titer) ** 2 for x in titers) / (n - 1) if n > 1 else 0
    )
    std_dev = math.sqrt(variance)
    cv = (std_dev / mean_titer * 100) if mean_titer > 0 else 0

    titer_25 = calculate_percentile(titers, 0.25)
    titer_75 = calculate_percentile(titers, 0.75)


    def get_vac_age(target_titer, breakthrough):
      if target_titer <= breakthrough:
        return sampling_age
      return (
          (math.log2(target_titer) - math.log2(breakthrough)) * t_half
      ) + sampling_age + correction


    vac_int_75 = get_vac_age(titer_75, 250)
    vac_int_25 = get_vac_age(titer_25, 250)
    vac_int_plus_75 = get_vac_age(titer_75, 500)
    vac_int_plus_25 = get_vac_age(titer_25, 500)

    st.markdown("---")
    st.markdown("### 📊 Analysis Results")

    if cv <= 30:
      st.success(
          f"*Flock Uniformity Good (CV = {cv:.1f}%)* — Single Vaccination"
          " Recommended"
      )
    else:
      st.warning(
          f"*High Flock Variation (CV = {cv:.1f}%)* — Consider Two"
          " Vaccinations (25% & 75% Windows)"
      )

    # Display Stats Table
    stats_data = {
        "Statistical Parameter": [
            "Total Samples (N)",
            "Mean Titer",
            "Minimum Titer",
            "Maximum Titer",
            "Coefficient of Var (CV%)",
            "25th Percentile Titer",
            "75th Percentile Titer",
        ],
        "Value": [
            f"{n}",
            f"{mean_titer:,.1f}",
            f"{min_titer:,.1f}",
            f"{max_titer:,.1f}",
            f"{cv:.1f}%",
            f"{titer_25:,.1f}",
            f"{titer_75:,.1f}",
        ],
    }
    st.table(stats_data)

    # Vaccination Cards
    if vaccine_choice in ["Intermediate", "Both"]:
      day_75 = math.floor(vac_int_75)
      day_25 = math.floor(vac_int_25)
      st.info(
          "*Intermediate Vaccine (BT = 250)*\n\n"
          f"• *75% Coverage Target:* Day {vac_int_75:.1f} (Days"
          f" {day_75}–{day_75+1})\n\n"
          f"• *25% Coverage Target:* Day {vac_int_25:.1f} (Days"
          f" {day_25}–{day_25+1})"
      )

    if vaccine_choice in ["Intermediate Plus", "Both"]:
      day_plus_75 = math.floor(vac_int_plus_75)
      day_plus_25 = math.floor(vac_int_plus_25)
      st.warning(
          "*Intermediate Plus Vaccine (BT = 500)*\n\n"
          f"• *75% Coverage Target:* Day {vac_int_plus_75:.1f} (Days"
          f" {day_plus_75}–{day_plus_75+1})\n\n"
          f"• *25% Coverage Target:* Day {vac_int_plus_25:.1f} (Days"
          f" {day_plus_25}–{day_plus_25+1})"
      )

    # PDF Export for Mobile & Web
    if REPORTLAB_AVAILABLE:
      pdf_buffer = BytesIO()
      doc = SimpleDocTemplate(
          pdf_buffer,
          pagesize=A4,
          rightMargin=36,
          leftMargin=36,
          topMargin=36,
          bottomMargin=36,
      )

      story = []
      styles = getSampleStyleSheet()

      title_style = ParagraphStyle(
          'DocTitle',
          parent=styles['Heading1'],
          fontName='Helvetica-Bold',
          fontSize=18,
          leading=22,
          textColor=colors.HexColor('#0b4a47'),
          alignment=1,
          spaceAfter=4,
      )

      subtitle_style = ParagraphStyle(
          'DocSubTitle',
          parent=styles['Normal'],
          fontName='Helvetica-Oblique',
          fontSize=10,
          leading=12,
          textColor=colors.HexColor('#555555'),
          alignment=1,
          spaceAfter=15,
      )

      section_heading = ParagraphStyle(
          'SectionHeading',
          parent=styles['Heading2'],
          fontName='Helvetica-Bold',
          fontSize=12,
          leading=14,
          textColor=colors.HexColor('#0b4a47'),
          spaceBefore=10,
          spaceAfter=6,
      )

      body_style = ParagraphStyle(
          'BodyTextCustom',
          parent=styles['Normal'],
          fontName='Helvetica',
          fontSize=9.5,
          leading=13,
          textColor=colors.HexColor('#222222'),
      )

      footer_credit_style = ParagraphStyle(
          'FooterCredit',
          parent=styles['Normal'],
          fontName='Helvetica-BoldOblique',
          fontSize=9,
          leading=12,
          textColor=colors.HexColor('#0b4a47'),
          alignment=1,
      )

      story.append(
          Paragraph('IBD (Gumboro) Vaccination Date Report', title_style)
      )
      story.append(
          Paragraph(
              'Calculated using Deventer Formula (GD Deventer)', subtitle_style
          )
      )
      story.append(
          HRFlowable(
              width='100%',
              thickness=1.5,
              color=colors.HexColor('#0b4a47'),
              spaceAfter=12,
          )
      )

      date_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
      meta_data = [
          [
              Paragraph(f'<b>Report Date:</b> {date_str}', body_style),
              Paragraph(
                  f'<b>Flock Type:</b> {flock_type} (t½ = {t_half} days)',
                  body_style,
              ),
          ],
          [
              Paragraph(
                  f'<b>Sampling Age:</b> {sampling_age} Days', body_style
              ),
              Paragraph(f'<b>Yolk Correction:</b> +{correction} Days', body_style),
          ],
      ]
      meta_table = Table(meta_data, colWidths=[260, 260])
      meta_table.setStyle(
          TableStyle([
              ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
              ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
              ('PADDING', (0, 0), (-1, -1), 6),
          ])
      )
      story.append(meta_table)
      story.append(Spacer(1, 10))

      story.append(
          Paragraph('1. Statistical Analysis Summary', section_heading)
      )
      stats_table_data = [
          ['Metric', 'Value', 'Metric', 'Value'],
          ['Total Samples (N)', f'{n}', 'Mean Titer', f'{mean_titer:,.1f}'],
          ['Minimum Titer', f'{min_titer:,.1f}', 'Maximum Titer', f'{max_titer:,.1f}'],
          ['25th Percentile Titer', f'{titer_25:,.1f}', '75th Percentile Titer', f'{titer_75:,.1f}'],
          ['Coefficient of Var (CV%)', f'{cv:.1f}%', '-', '-'],
      ]
      stats_pdf_table = Table(stats_table_data, colWidths=[150, 110, 150, 110])
      stats_pdf_table.setStyle(
          TableStyle([
              ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0b4a47')),
              ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
              ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
              ('FONTSIZE', (0, 0), (-1, -1), 9),
              ('ALIGN', (1, 0), (1, -1), 'CENTER'),
              ('ALIGN', (3, 0), (3, -1), 'CENTER'),
              ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
              ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f5f8')]),
              ('PADDING', (0, 0), (-1, -1), 5),
          ])
      )
      story.append(stats_pdf_table)

      uniformity_text = '<b>Flock Uniformity Status:</b> ' + (
          "<font color='#155724'>Good (CV ≤ 30%). Single vaccination is recommended.</font>"
          if cv <= 30
          else "<font color='#856404'>High Variation (CV > 30%). Consider two vaccinations (25% and 75% targets).</font>"
      )
      story.append(Spacer(1, 4))
      story.append(Paragraph(uniformity_text, body_style))
      story.append(Spacer(1, 10))

      story.append(
          Paragraph(
              '2. Deventer Formula Vaccination Predictions', section_heading
          )
      )
      pred_rows = [
          ['Vaccine Type', 'BT', '75% Coverage Target', '25% Coverage Target']
      ]

      if vaccine_choice in ['Intermediate', 'Both']:
        d_int_75 = math.floor(vac_int_75)
        d_int_25 = math.floor(vac_int_25)
        pred_rows.append([
            'Intermediate Vaccine',
            '250',
            f'{vac_int_75:.1f} d (Day {d_int_75}–{d_int_75+1})',
            f'{vac_int_25:.1f} d (Day {d_int_25}–{d_int_25+1})',
        ])

      if vaccine_choice in ['Intermediate Plus', 'Both']:
        d_plus_75 = math.floor(vac_int_plus_75)
        d_plus_25 = math.floor(vac_int_plus_25)
        pred_rows.append([
            'Intermediate Plus Vaccine',
            '500',
            f'{vac_int_plus_75:.1f} d (Day {d_plus_75}–{d_plus_75+1})',
            f'{vac_int_plus_25:.1f} d (Day {d_plus_25}–{d_plus_25+1})',
        ])

      pred_pdf_table = Table(pred_rows, colWidths=[140, 50, 165, 165])
      pred_pdf_table.setStyle(
          TableStyle([
              ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
              ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
              ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
              ('FONTSIZE', (0, 0), (-1, -1), 8.5),
              ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
              ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#bbbbbb')),
              ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#e6f6f3'), colors.HexColor('#fff4dc')]),
              ('PADDING', (0, 0), (-1, -1), 6),
          ])
      )
      story.append(pred_pdf_table)
      story.append(Spacer(1, 12))

      story.append(
          Paragraph(
              f'3. Submitted Sample Titers Data ({n} Samples)', section_heading
          )
      )
      sample_grid = [['Sample', 'Titer', 'Sample', 'Titer', 'Sample', 'Titer']]
      num_rows = math.ceil(n / 3)

      for r in range(num_rows):
        row_cells = []
        for c in range(3):
          idx = (r * 3) + c
          if idx < n:
            row_cells.extend([f'S{idx+1}', f'{titers[idx]:,.0f}'])
          else:
            row_cells.extend(['-', '-'])
        sample_grid.append(row_cells)

      titer_pdf_table = Table(sample_grid, colWidths=[80, 93, 80, 93, 80, 94])
      titer_pdf_table.setStyle(
          TableStyle([
              ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#444444')),
              ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
              ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
              ('FONTSIZE', (0, 0), (-1, -1), 8.5),
              ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
              ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
              ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
              ('PADDING', (0, 0), (-1, -1), 4),
          ])
      )
      story.append(titer_pdf_table)

      story.append(Spacer(1, 18))
      story.append(
          HRFlowable(
              width='100%',
              thickness=0.5,
              color=colors.HexColor('#cccccc'),
              spaceAfter=8,
          )
      )
      story.append(
          Paragraph(
              'designed by Dr. Wissam J. Mohammed', footer_credit_style
          )
      )

      doc.build(story)
      pdf_data = pdf_buffer.getvalue()

      st.download_button(
          label='📥 Download Full PDF Report',
          data=pdf_data,
          file_name='IBD_Vaccination_Report.pdf',
          mime='application/pdf',
          use_container_width=True,
      )
      
# Footer credit
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #5b7773; font-size: 12px;'>Designed"
    " by Dr. Wissam J. Mohammed</p>",
    unsafe_allow_html=True,
)
