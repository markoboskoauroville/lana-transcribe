import streamlit as st
import requests
import time
import os
import tempfile

# ── API key ───────────────────────────────────────────────────────────────────
API_KEY = st.secrets["ASSEMBLYAI_API_KEY"]
HEADERS = {"authorization": API_KEY}

# ── Dizajn ────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Lana Transcribe", page_icon="🎙️", layout="centered")
st.markdown('<div style="position:fixed;top:8px;left:12px;color:#444;font-size:11px;z-index:9999;">v1.2</div>', unsafe_allow_html=True)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #1a1a1a; color: #e0e0e0; }
  .stApp { background-color: #1a1a1a; }
  h1 { color: #00aaff; font-weight: 700; letter-spacing: 1px; border-bottom: 2px solid #00aaff; padding-bottom: 8px; margin-bottom: 4px; }
  .subtitle { color: #888; font-size: 0.85rem; margin-bottom: 24px; letter-spacing: 2px; text-transform: uppercase; }
  .stRadio > label { color: #aaa; font-size: 0.8rem; letter-spacing: 1px; text-transform: uppercase; }
  .stRadio div[role="radiogroup"] label { color: #ccc; }
  .stButton > button { background-color: #00aaff; color: #000; font-weight: 700; border: none; border-radius: 4px; padding: 10px 28px; letter-spacing: 1px; text-transform: uppercase; }
  .stButton > button:hover { background-color: #0088cc; color: #fff; }
  .stTextArea textarea { background-color: #2a2a2a; color: #e0e0e0; border: 1px solid #444; font-family: 'Courier New', monospace; font-size: 0.9rem; }
  .stDownloadButton > button { background-color: #222; color: #00aaff; border: 1px solid #00aaff; border-radius: 4px; font-weight: 600; }
  .stDownloadButton > button:hover { background-color: #00aaff; color: #000; }
  .status-box { background-color: #222; border-left: 3px solid #00aaff; padding: 10px 16px; border-radius: 4px; margin: 12px 0; font-size: 0.9rem; color: #aaa; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>🎙️ LANA TRANSCRIBE</h1>", unsafe_allow_html=True)
st.markdown('<div class="subtitle">Nova TV — Automated Interview Transcription</div>', unsafe_allow_html=True)

# ── Jezik ─────────────────────────────────────────────────────────────────────
LANGUAGE_MAP = {
    "Hrvatski": "hr",
    "English":  "en",
    "Italiano": "it",
    "Deutsch":  "de",
    "Français": "fr",
}
lang_label = st.radio("JEZIK / LANGUAGE", list(LANGUAGE_MAP.keys()), horizontal=True)
lang_code  = LANGUAGE_MAP[lang_label]

# ── Timecode ─────────────────────────────────────────────────────────────────
timecode_option  = st.radio("TIMECODE U TEKSTU", ["Bez timecoda", "S timecodeom"], horizontal=True)
include_timecode = timecode_option == "S timecodeom"

st.markdown("---")

# ── Upload ────────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "Učitaj audio datoteku",
    type=["mp3", "mp4", "wav", "m4a", "aac", "ogg", "flac", "mov", "mxf"],
    help="Podržani formati: MP3, MP4, WAV, M4A, AAC, OGG, FLAC, MOV, MXF"
)

# ── Timecode helper ───────────────────────────────────────────────────────────
def ms_to_tc(ms):
    total_s = ms // 1000
    h  = total_s // 3600
    m  = (total_s % 3600) // 60
    s  = total_s % 60
    cs = (ms % 1000) // 10
    return f"{h:02d}:{m:02d}:{s:02d}.{cs:02d}"

# ── Transkripcija ─────────────────────────────────────────────────────────────
if uploaded_file is not None:
    st.markdown(
        f'<div class="status-box">📂 <strong>{uploaded_file.name}</strong> — Jezik: <strong>{lang_label}</strong></div>',
        unsafe_allow_html=True
    )

    if st.button("▶  POKRETANJE TRANSKRIPCIJE"):

        try:
            # KORAK 1 — Upload datoteke na AssemblyAI
            with st.spinner("📤 Uploading audio na AssemblyAI..."):
                upload_response = requests.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers={**HEADERS, "content-type": "application/octet-stream"},
                    data=uploaded_file.read()
                )
                upload_response.raise_for_status()
                upload_url = upload_response.json()["upload_url"]

            st.info("✓ Audio uploadano. Pokrećem transkripciju...")

            # KORAK 2 — Zahtjev za transkripciju
            transcript_request = {
                "audio_url":     upload_url,
                "language_code": lang_code,
                "speech_model":  "universal-2",
                "punctuate":     True,
                "format_text":   True,
            }

            transcript_response = requests.post(
                "https://api.assemblyai.com/v2/transcript",
                headers={**HEADERS, "content-type": "application/json"},
                json=transcript_request
            )
            transcript_response.raise_for_status()
            transcript_id = transcript_response.json()["id"]

            # KORAK 3 — Polling dok ne završi
            polling_url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
            status_placeholder = st.empty()
            attempts = 0

            while True:
                time.sleep(3)
                poll = requests.get(polling_url, headers=HEADERS).json()
                status = poll.get("status")
                attempts += 1
                elapsed = attempts * 3
                status_placeholder.info(f"⏳ Transkripcija u tijeku... ({elapsed}s)")

                if status == "completed":
                    status_placeholder.empty()
                    break
                elif status == "error":
                    st.error(f"AssemblyAI greška: {poll.get('error', 'Nepoznata greška')}")
                    st.stop()
                elif attempts > 120:
                    st.error("Timeout — audio je prevelik ili predugo traje.")
                    st.stop()

            # KORAK 4 — Gradi output
            if include_timecode and poll.get("words"):
                words = poll["words"]
                lines = []
                current_words = []
                current_start = words[0]["start"]

                for i, word in enumerate(words):
                    current_words.append(word["text"])
                    if len(current_words) >= 10 or i == len(words) - 1:
                        tc = ms_to_tc(current_start)
                        lines.append(f"[{tc}]  {' '.join(current_words)}")
                        current_words = []
                        if i < len(words) - 1:
                            current_start = words[i + 1]["start"]

                output_text = "\n\n".join(lines)
            else:
                output_text = poll.get("text", "")

            # KORAK 5 — Prikaži i omogući download
            st.success("✅ Transkripcija završena!")
            st.text_area("REZULTAT", output_text, height=400)

            base_name = os.path.splitext(uploaded_file.name)[0]
            tc_suffix = "_timecode" if include_timecode else ""
            download_filename = f"{base_name}_{lang_code}{tc_suffix}.txt"

            st.download_button(
                label="⬇  PREUZMI TXT DATOTEKU",
                data=output_text.encode("utf-8"),
                file_name=download_filename,
                mime="text/plain"
            )

        except requests.exceptions.HTTPError as e:
            st.error(f"HTTP greška: {e.response.status_code} — {e.response.text}")
        except Exception as e:
            st.error(f"Greška: {str(e)}")
