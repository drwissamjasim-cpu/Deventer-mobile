import datetime
import math
import os
import random
import re
import tempfile
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
# APP STYLING & VERTICAL PORTRAIT CAMERA CSS
# ==========================================
st.markdown(
    """
    <style>
    .main { background-color: #eaf4f2; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: bold; min-height: 42px; }
    
    /* Force Camera Input into a clean Vertical (Portrait) Box */
    [data-testid="stCameraInput"] {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 100% !important;
    }
    [data-testid="stCameraInput"] video, [data-testid="stCameraInput"] img {
        width: 100% !important;
        max-width: 420px !important;
        aspect-ratio: 3 / 4 !important;
        object-fit: cover !important;
        border-radius: 12px;
    }
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
st.markdown("---")
st.markdown("### 🧫 Titer Data Input")
input_mode = st.radio(
    "Choose Input Method",
    ["Manual Entry", "Upload PDF Report", "Capture Report with Camera"],
    horizontal=True,
)

titers = []

if input_mode == "Manual Entry":
  if "num_samples" not in st.session_state:
    st.session_state.num_samples = 18

  st.markdown(
      f"**Total Samples: {st.session_state.num_samples}** (Min required: 5)"
  )

  row1_col1, row1_col2, row1_col3 = st.columns(3)
  with row1_col1:
    if st.button("➕ Add 1"):
      st.session_state.num_samples += 1
      st.rerun()
  with row1_col2:
    if st.button("➕ Add 6"):
      st.session_state.num_samples += 6
      st.rerun()
  with row1_col3:
    if st.button("➖ Remove") and st.session_state.num_samples > 5:
      st.session_state.num_samples -= 1
      st.rerun()

  row2_col1, row2_col2 = st.columns(2)
  with row2_col1:
    if st.button("⚡ Fill Demo Data"):
      demo_vals = [
          4500,
          5200,
          6100,
          3800,
          7200,
          5900,
          6400,
          4100,
          5500,
          6800,
          7000,
          4800,
          5300,
          6000,
          4900,
          5800,
          6200,
          5100,
      ]
      for i in range(st.session_state.num_samples):
        st.session_state[f"t_val_{i}"] = str(
            demo_vals[i % len(demo_vals)] + random.randint(-150, 150)
        )
      st.rerun()
  with row2_col2:
    if st.button("🗑️ Clear All"):
      for i in range(st.session_state.num_samples):
        st.session_state[f"t_val_{i}"] = ""
      st.rerun()

  st.markdown("<br>", unsafe_allow_html=True)

  grid_cols = st.columns(2)
  for i in range(st.session_state.num_samples):
    col_idx = i % 2
    key = f"t_val_{i}"
    if key not in st.session_state:
      default_demo = [
          4500,
          5200,
          6100,
          3800,
          7200,
          5900,
          6400,
          4100,
          5500,
          6800,
          7000,
          4800,
      ]
      st.session_state[key] = (
          str(default_demo[i % len(default_demo)])
          if i < len(default_demo)
          else "5000"
      )

    with grid_cols[col_idx]:
      val_str = st.text_input(f"Sample #{i+1}", key=key)
      if val_str.strip():
        try:
          v = float(val_str.strip())
          if v >= 0:
            titers.append(v)
        except ValueError:
          pass

elif input_mode == "Upload PDF Report":
  uploaded_file = st.file_uploader("Upload ELISA PDF Report", type=["pdf"])
  if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
      tmp.write(uploaded_file.getvalue())
      tmp_path = tmp.name

    try:
      if PDFPLUMBER_AVAILABLE:
        with pdfplumber.open(tmp_path) as pdf:
          for page in pdf.pages:
            txt = page.extract_text() or ""
            found = re.findall(r"\b([1-9]\d{3,4})\b", txt)
            for f in found:
              val = float(f)
              if 100 <= val <= 45000:
                titers.append(val)
      st.success(f"Successfully extracted {len(titers)} titers from PDF!")
    except Exception as e:
      st.error(f"Error reading PDF: {e}")
    finally:
      if os.path.exists(tmp_path):
        os.remove(tmp_path)

else:  # Vertical Camera Capture Mode for Mobile
  st.markdown(
      "📱 **Vertical Camera Mode:** Hold your phone vertically (portrait)"
      " slightly back from the A4 paper so the text stays sharp and focused."
  )
  camera_image = st.camera_input("Capture A4 Report")
  if camera_image:
    img = Image.open(camera_image)
    st.image(
        img,
        caption="Captured Vertical Report Preview",
        use_container_width=True,
    )
    st.success("Photo captured successfully in portrait mode!")
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


st.markdown("---")
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

    st.markdown("### 📊 Analysis Results")

    if cv <= 30:
      st.success(
          f"**Flock Uniformity Good (CV = {cv:.1f}%)** — Single Vaccination"
          " Recommended"
      )
    else:
      st.warning(
          f"**High Flock Variation (CV = {cv:.1f}%)** — Consider Two"
          " Vaccinations (25% & 75% Windows)"
      )

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

    if vaccine_choice in ["Intermediate", "Both"]:
      day_75 = math.floor(vac_int_75)
      day_25 = math.floor(vac_int_25)
      st.info(
          "**Intermediate Vaccine (BT = 250)**\n\n"
          f"• **75% Coverage Target:** Day {vac_int_75:.1f} (Days"
          f" {day_75}–{day_75+1})\n\n"
          f"• **25% Coverage Target:** Day {vac_int_25:.1f} (Days"
          f" {day_25}–{day_25+1})"
      )

    if vaccine_choice in ["Intermediate Plus", "Both"]:
      day_plus_75 = math.floor(vac_int_plus_75)
      day_plus_25 = math.floor(vac_int_plus_25)
      st.warning(
          "**Intermediate Plus Vaccine (BT = 500)**\n\n"
          f"• **75% Coverage Target:** Day {vac_int_plus_75:.1f} (Days"
          f" {day_plus_75}–{day_plus_75+1})\n\n"
          f"• **25% Coverage Target:** Day {vac_int_plus_25:.1f} (Days"
          f" {day_plus_25}–{day_plus_25+1})"
      )

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

      story.append(
          Paragraph(
              "<b>IBD (Gumboro) Vaccination Date Report</b>",
              styles["Heading1"],
          )
      )
      story.append(
          Paragraph(
              f"Flock Type: {flock_type} | Sampling Age: {sampling_age} Days",
              styles["Normal"],
          )
      )
      story.append(Spacer(1, 10))
      story.append(
          Paragraph(
              f"<b>Mean Titer:</b> {mean_titer:,.1f} | <b>CV%:</b> {cv:.1f}%",
              styles["Normal"],
          )
      )
      doc.build(story)
      pdf_data = pdf_buffer.getvalue()

      st.download_button(
          label="📥 Download PDF Report",
          data=pdf_data,
          file_name="IBD_Vaccination_Report.pdf",
          mime="application/pdf",
          use_container_width=True,
      )

# Footer credit
st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #5b7773; font-size: 12px;'>Designed"
    " by Dr. Wissam J. Mohammed</p>",
    unsafe_allow_html=True,
)
