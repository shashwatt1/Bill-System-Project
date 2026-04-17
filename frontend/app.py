"""Streamlit UI for Document OCR extraction."""

import streamlit as st
import requests
from PIL import Image
import io
import json

# ── Config ──
API_URL = "http://localhost:8000/api/v1/extract"

st.set_page_config(
    page_title="DocOCR — Text Extraction",
    page_icon="📄",
    layout="centered",
)

# ── Custom Styling ──
st.markdown("""
<style>
    .stApp { max-width: 800px; margin: 0 auto; }
    .confidence-high { color: #22c55e; font-weight: 600; }
    .confidence-med  { color: #f59e0b; font-weight: 600; }
    .confidence-low  { color: #ef4444; font-weight: 600; }
    div[data-testid="stFileUploader"] > div { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

# ── Header ──
st.title("📄 DocOCR")
st.caption("Upload an invoice or bill image → get structured text back.")

st.divider()

# ── File Upload ──
uploaded = st.file_uploader(
    "Choose an image",
    type=["jpg", "jpeg", "png", "bmp", "tiff", "webp"],
    help="Max 10 MB. Supported: JPG, PNG, BMP, TIFF, WEBP",
)

if uploaded:
    # Show preview
    col1, col2 = st.columns([1, 1.4])
    with col1:
        image = Image.open(uploaded)
        st.image(image, caption=uploaded.name, use_container_width=True)
    with col2:
        st.markdown(f"**File:** `{uploaded.name}`")
        st.markdown(f"**Size:** `{uploaded.size / 1024:.1f} KB`")
        st.markdown(f"**Dimensions:** `{image.size[0]} × {image.size[1]}`")

    # Extract button
    if st.button("🔍 Extract Text", type="primary", use_container_width=True):
        with st.spinner("Running OCR..."):
            try:
                uploaded.seek(0)
                files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                resp = requests.post(API_URL, files=files, timeout=60)

                if resp.status_code != 200:
                    detail = resp.json().get("detail", resp.text)
                    st.error(f"API error ({resp.status_code}): {detail}")
                else:
                    data = resp.json()
                    regions = data.get("regions", [])

                    st.success(f"Extracted **{len(regions)}** text regions")

                    if regions:
                        # Results table
                        st.subheader("Extracted Text")
                        for i, r in enumerate(regions, 1):
                            conf = r["confidence"]
                            if conf >= 0.9:
                                badge = "🟢"
                            elif conf >= 0.7:
                                badge = "🟡"
                            else:
                                badge = "🔴"

                            with st.container():
                                c1, c2 = st.columns([5, 1])
                                c1.markdown(f"`{i}.` {r['text']}")
                                c2.markdown(f"{badge} `{conf:.2%}`")

                        st.divider()

                        # Raw JSON
                        with st.expander("📋 Raw JSON Response"):
                            st.json(data)

                        # Copy-friendly text
                        with st.expander("📝 Plain Text (copy-friendly)"):
                            plain = "\n".join(r["text"] for r in regions)
                            st.code(plain, language=None)
                    else:
                        st.warning("No text regions detected in this image.")

            except requests.ConnectionError:
                st.error(
                    "Cannot connect to backend. "
                    "Make sure the server is running: `cd backend && python run.py`"
                )
            except Exception as e:
                st.error(f"Unexpected error: {e}")
