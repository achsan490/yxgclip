# ==============================================================================
# CLIPPER STUDIO v3.0 — AUTO MULTI-CLIP YOUTUBE CLIPPER
# ==============================================================================
# Fitur Utama:
# 1. Deteksi otomatis momen menarik (Chapters + Most Replayed Heatmap + Fallback)
# 2. Preview clip via YouTube embed (tanpa download penuh)
# 3. Multi-clip selection — pilih & export beberapa clip sekaligus
# 4. Subtitle otomatis dari YouTube auto-captions (burn via FFmpeg)
# 5. Portrait 9:16 dengan background fill: blur/solid/gradient/image
# 6. Overlay info bar: judul, channel, hashtag, watermark
# ==============================================================================

import streamlit as st
import streamlit.components.v1 as components
import yt_dlp
import os
import time
import glob
import subprocess
import shutil
from yt_dlp.utils import download_range_func  # kept for potential future use

# ==============================================================================
# KONFIGURASI API
# ==============================================================================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = st.secrets.get("GEMINI_MODEL", "gemini-1.5-flash")

WHISPER_TYPE = None
WHISPER_AVAILABLE = False

def check_whisper_available():
    global WHISPER_AVAILABLE, WHISPER_TYPE
    if WHISPER_AVAILABLE:
        return True
    try:
        from faster_whisper import WhisperModel # type: ignore
        WHISPER_AVAILABLE = True
        WHISPER_TYPE = 'faster'
        return True
    except Exception:
        try:
            import whisper # type: ignore
            WHISPER_AVAILABLE = True
            WHISPER_TYPE = 'openai'
            return True
        except Exception:
            WHISPER_AVAILABLE = False
            return False

@st.cache_resource
def load_whisper_model(model_size="base"):
    """Load Whisper model sekali saja (cached) berdasarkan ukuran."""
    if not check_whisper_available():
        return None
    try:
        if WHISPER_TYPE == 'faster':
            from faster_whisper import WhisperModel # type: ignore
            return WhisperModel(model_size, device="cpu", compute_type="int8")
        elif WHISPER_TYPE == 'openai':
            import whisper # type: ignore
            return whisper.load_model(model_size, device="cpu")
    except Exception:
        return None

# ==============================================================================
# 1. KONFIGURASI HALAMAN
# ==============================================================================
st.set_page_config(
    page_title="YXGClip — YouTube Auto Clipper",
    page_icon="✂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. CSS PREMIUM v3.0 — MODERN GRADIENT DESIGN
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');

    :root {
        --bg:         #000000;
        --bg-raised:  #121212;
        --bg-card:    #16161a;
        --bg-input:   #1e1e24;
        --border:         rgba(255,255,255,0.06);
        --border-mid:     rgba(255,255,255,0.12);
        --border-focus:   rgba(234,179,8,0.55);
        --accent:         #eab308;
        --accent-dim:     rgba(234,179,8,0.08);
        --accent-border:  rgba(234,179,8,0.18);
        --green:      #30d158;
        --amber:      #ff9f0a;
        --text-1: #ffffff;
        --text-2: #a1a1a6;
        --text-3: #86868b;
    }

    html, body, [class*="css"] {
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
    }
    .stApp {
        background-color: var(--bg) !important;
        color: var(--text-1);
        background-image: 
            radial-gradient(circle at 0% 0%, rgba(234, 179, 8, 0.04) 0%, transparent 40%),
            radial-gradient(circle at 100% 100%, rgba(234, 179, 8, 0.02) 0%, transparent 40%) !important;
        background-attachment: fixed !important;
    }
    .stApp > header { background: var(--bg-raised) !important; border-bottom: 1px solid var(--border) !important; }
    #MainMenu, footer { visibility: hidden; }

    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 99px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.18); }

    /* SIDEBAR */
    section[data-testid="stSidebar"] { background: var(--bg-raised) !important; border-right: 1px solid var(--border) !important; }
    .sidebar-section { 
        font-size: 0.62rem; 
        font-weight: 700; 
        text-transform: uppercase; 
        letter-spacing: 1.5px; 
        color: var(--text-2); 
        margin: 22px 0 8px; 
        padding-left: 8px; 
        border-left: 2px solid var(--accent); 
    }

    /* HERO */
    .hero-wrap { text-align: center; padding: 8px 0 2px; }
    .hero-eyebrow { display: inline-block; font-size: 0.65rem; font-weight: 600; color: var(--accent); letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px; opacity: 0.8; }
    .hero-title { font-size: clamp(1.5rem, 3.5vw, 2.1rem); font-weight: 800; color: var(--text-1); letter-spacing: -0.7px; line-height: 1.15; margin: 0 0 7px; }
    .hero-title em { font-style: normal; color: var(--accent); }
    .hero-sub { font-size: 0.86rem; color: var(--text-2); line-height: 1.6; margin-bottom: 18px; }

    /* STEP TRACK */
    .step-track { display: flex; align-items: center; justify-content: center; gap: 0; margin: 18px 0 24px; }
    .step-node { display: flex; flex-direction: column; align-items: center; gap: 6px; min-width: 100px; z-index: 2; }
    .step-circle {
        width: 30px; height: 30px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 0.78rem;
        border: 1.5px solid var(--border);
        background: var(--bg-raised); color: var(--text-3);
        transition: all 0.2s;
    }
    .step-circle.done  { background: var(--accent); border-color: var(--accent); color: #fff; }
    .step-circle.active { background: var(--bg-card); border-color: var(--accent); color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim); }
    .step-label { font-size: 0.64rem; font-weight: 600; letter-spacing: 0.3px; text-align: center; text-transform: uppercase; }
    .step-label.done, .step-label.active { color: var(--accent); }
    .step-label.pending { color: var(--text-3); }
    .step-line { flex: 1; height: 1px; min-width: 30px; margin: 0 -5px; margin-bottom: 20px; background: var(--border); z-index: 1; }
    .step-line.done { background: var(--accent); }

    /* CARDS */
    .glass-card {
        background: rgba(29, 33, 48, 0.45) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 14px !important;
        padding: 18px 20px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
        animation: fadeUp 0.25s ease both;
    }
    .glass-card:hover { 
        border-color: rgba(79, 156, 249, 0.2) !important;
        box-shadow: 0 8px 32px 0 rgba(79, 156, 249, 0.03) !important;
    }
    .card-header { display: flex; align-items: center; gap: 11px; margin-bottom: 10px; }
    .card-icon { width: 34px; height: 34px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 0.95rem; flex-shrink: 0; background: var(--accent-dim); border: 1px solid var(--accent-border); }
    .card-title { font-size: 0.88rem; font-weight: 700; color: var(--text-1); margin: 0 0 1px; letter-spacing: -0.2px; }
    .card-desc  { font-size: 0.73rem; color: var(--text-2); margin: 0; }

    /* META GRID */
    .meta-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(85px, 1fr)); gap: 8px; margin-top: 12px; }
    .meta-item { background: var(--bg-raised); border: 1px solid var(--border); border-radius: 8px; padding: 11px 8px; text-align: center; }
    .meta-value { font-size: 1rem; font-weight: 700; color: var(--text-1); margin-bottom: 2px; font-feature-settings: "tnum"; }
    .meta-key { font-size: 0.58rem; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.8px; font-weight: 700; }
    .meta-title-text { font-size: 0.86rem; font-weight: 500; color: var(--text-2); margin-top: 10px; line-height: 1.5; padding-left: 10px; border-left: 2px solid var(--accent); }

    /* CLIP CARDS */
    .clip-card { background: var(--bg-raised); border: 1px solid var(--border); border-radius: 9px; padding: 11px 13px; margin-bottom: 7px; transition: border-color 0.15s; }
    .clip-card:hover { border-color: var(--border-mid); }
    .clip-title { font-size: 0.84rem; font-weight: 600; color: var(--text-1); margin-bottom: 5px; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .clip-meta { font-size: 0.73rem; color: var(--text-2); }
    .clip-badge { display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 0.57rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; flex-shrink: 0; }
    .badge-chapter    { background: rgba(6,182,212,0.1);   color: #22d3ee; border: 1px solid rgba(6,182,212,0.2); }
    .badge-heatmap    { background: rgba(245,166,35,0.12);  color: #f5a623; border: 1px solid rgba(245,166,35,0.25); }
    .badge-auto       { background: rgba(139,149,168,0.08); color: #8b95a8; border: 1px solid rgba(139,149,168,0.18); }
    .badge-ai         { background: var(--accent-dim); color: var(--accent); border: 1px solid var(--accent-border); }
    .badge-transcript { background: rgba(52,199,123,0.1);  color: #34c77b; border: 1px solid rgba(52,199,123,0.2); }

    /* TIME PILL */
    .time-pill { display: inline-flex; align-items: center; gap: 4px; background: var(--bg); border: 1px solid var(--border); border-radius: 5px; padding: 2px 7px; font-size: 0.7rem; font-family: 'DM Mono', monospace; }
    .time-pill .tv { font-weight: 500; color: var(--text-1); }
    .time-pill .ts { color: var(--text-3); }

    /* VIRAL SCORE */
    .viral-bar-wrap { background: var(--bg-raised); border: 1px solid var(--border); border-radius: 9px; padding: 11px 13px; margin-bottom: 9px; }
    .viral-bar-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .viral-bar-label { font-size: 0.7rem; font-weight: 600; color: var(--text-2); }
    .viral-bar-score { font-size: 0.86rem; font-weight: 800; color: var(--text-1); font-feature-settings: "tnum"; }
    .viral-bar-track { background: var(--bg); height: 3px; border-radius: 2px; overflow: hidden; }
    .viral-bar-fill { height: 100%; border-radius: 2px; background: var(--accent); transition: width 0.6s cubic-bezier(0.4,0,0.2,1); }

    /* BUTTONS */
    div.stButton > button, div.stFormSubmitButton > button {
        background: var(--accent) !important; color: #fff !important; border: none !important;
        padding: 9px 16px !important; border-radius: 8px !important;
        font-weight: 600 !important; font-size: 0.85rem !important;
        font-family: 'Inter', sans-serif !important; width: 100% !important;
        transition: background 0.15s !important; box-shadow: none !important;
        letter-spacing: -0.1px !important;
        cursor: pointer !important;
    }
    div.stButton > button:hover, div.stFormSubmitButton > button:hover { background: #6aaaf9 !important; transform: none !important; box-shadow: none !important; }
    div.stButton > button:active, div.stFormSubmitButton > button:active { opacity: 0.85 !important; }
    div.stDownloadButton > button {
        background: var(--bg-card) !important; color: var(--text-1) !important;
        border: 1px solid var(--border) !important; border-radius: 8px !important;
        font-weight: 600 !important; padding: 9px 16px !important;
        transition: all 0.15s !important; box-shadow: none !important;
        cursor: pointer !important;
    }
    div.stDownloadButton > button:hover { border-color: var(--border-mid) !important; background: rgba(255,255,255,0.04) !important; }

    /* FORM INPUTS */
    .stTextInput > div > div > input, .stNumberInput > div > div > input {
        background: var(--bg-input) !important; border: 1px solid var(--border) !important;
        border-radius: 8px !important; color: var(--text-1) !important;
        padding: 9px 12px !important; font-size: 0.88rem !important;
        box-shadow: none !important; transition: border-color 0.15s !important;
    }
    .stTextInput > div > div > input:focus, .stNumberInput > div > div > input:focus {
        border-color: var(--border-focus) !important;
        box-shadow: 0 0 0 3px rgba(79,156,249,0.08) !important;
    }
    .stSelectbox > div > div {
        background: var(--bg-input) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        cursor: pointer !important;
    }
    .stSelectbox div[data-baseweb="select"],
    .stSelectbox div[role="button"],
    .stSelectbox select,
    .stSelectbox div,
    ul[role="listbox"] li,
    div[data-baseweb="menu"] div,
    div[role="option"],
    li[role="option"] {
        cursor: pointer !important;
    }
    .stTextArea > div > div > textarea { background: var(--bg-input) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; color: var(--text-1) !important; }
    .stSlider > div > div > div > div { background: var(--accent) !important; }
    div[data-testid="stAlert"] { border-radius: 8px !important; background: var(--bg-raised) !important; border: 1px solid var(--border) !important; }

    /* CHECKBOX, RADIO, TOGGLE POINTERS */
    div[data-testid="stCheckbox"] label,
    div[data-testid="stCheckbox"] input,
    div[data-testid="stCheckbox"] div,
    div[data-testid="stToggle"] label,
    div[data-testid="stToggle"] input,
    div[data-testid="stToggle"] div,
    div[data-testid="stRadio"] label,
    div[data-testid="stRadio"] input,
    div[data-testid="stRadio"] div {
        cursor: pointer !important;
    }

    /* EXPANDER */
    details { background: var(--bg-raised) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; padding: 0 !important; overflow: hidden !important; }
    summary,
    [data-testid="stExpander"] details summary,
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] details {
        padding: 11px 16px !important;
        font-weight: 600 !important;
        font-size: 0.84rem !important;
        cursor: pointer !important;
        color: var(--text-1) !important;
    }

    /* TABS */
    .stTabs [data-baseweb="tab-list"] { background: transparent !important; gap: 0 !important; border-bottom: 1px solid var(--border) !important; }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important; border: none !important; border-radius: 0 !important;
        color: var(--text-2) !important; font-weight: 600 !important; font-size: 0.8rem !important;
        padding: 7px 14px !important; border-bottom: 2px solid transparent !important;
        margin-bottom: -1px !important; transition: color 0.15s !important;
    }
    .stTabs [aria-selected="true"] { color: var(--text-1) !important; border-bottom-color: var(--accent) !important; }

    /* PORTRAIT FRAME */
    .portrait-frame-wrapper { display: flex; justify-content: center; }
    .portrait-frame { width: 200px; height: 355px; border-radius: 12px; border: 1px solid var(--border); overflow: hidden; background: #000; }

    /* SECTION DIVIDER */
    .section-divider { display: flex; align-items: center; gap: 12px; margin: 20px 0 16px; }
    .section-divider::before, .section-divider::after { content: ''; flex: 1; height: 1px; background: var(--border); }
    .section-divider-text { font-size: 0.65rem; color: var(--text-3); text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700; white-space: nowrap; }

    /* RESULT */
    .result-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--green); margin-right: 6px; position: relative; top: -1px; }
    .result-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }

    /* FILL TAG */
    .fill-preview-tag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px; border-radius: 5px; font-size: 0.67rem; font-weight: 700; background: var(--accent-dim); border: 1px solid var(--accent-border); color: var(--accent); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }

    /* FOOTER */
    .app-footer { text-align: center; padding: 18px 0 10px; color: var(--text-3); font-size: 0.7rem; border-top: 1px solid var(--border); margin-top: 40px; }
    .app-footer strong { color: var(--text-2); font-weight: 600; }

    /* ANIMATION */
    @keyframes fadeUp { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

    /* BORDERED CONTAINER CARD OVERRIDE */
    div[data-testid="stVerticalBlockBorder"] {
        background-color: rgba(29, 33, 48, 0.45) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
        border-radius: 14px !important;
        padding: 20px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    div[data-testid="stVerticalBlockBorder"]:hover {
        border-color: rgba(79, 156, 249, 0.2) !important;
        box-shadow: 0 8px 32px 0 rgba(79, 156, 249, 0.03) !important;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. FOLDER & SESSION STATE
# ==============================================================================
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

defaults = {
    'video_metadata': None,
    'current_url': "",
    'clips': [],
    'selected_clips': {},
    'subtitle_path': None,
    'subtitle_lang': None,
    'exported_files': {},
    'raw_video_files': {},
    'clip_srts': {},
    'clip_configs': {},
    'clip_srt_cues': {},
    'export_running': False,
    'preview_clip_index': 0,
    '_clips_target_dur': None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================================
# 4. UTILITY FUNCTIONS
# ==============================================================================

def generate_social_suggestions(clip, meta, srt_content=None):
    """Menghasilkan saran caption/judul dan hashtag untuk media sosial."""
    import re
    orig_title = meta.get('title', '')

    hook_text = ""
    if srt_content:
        cues = parse_srt_content(srt_content)
        hook_words = []
        for c in cues[:3]:
            text = c.get('text', '').strip()
            text_clean = re.sub(r'\{[^}]+\}', '', text)
            text_clean = text_clean.replace('\n', ' ')
            if text_clean:
                hook_words.append(text_clean)
        if hook_words:
            hook_text = " ".join(hook_words)
            if len(hook_text) > 60:
                hook_text = hook_text[:57] + "..."

    clip_name = clip.get('title', '').replace('🔥 ', '').replace('📖 ', '').replace('✂️ ', '')

    if hook_text:
        caption = f"\"{hook_text}\" 🎬 | Momen menarik dari: {orig_title}"
    else:
        caption = f"{clip_name} - {orig_title}"

    if len(caption) > 120:
        caption = caption[:117] + "..."

    words = re.findall(r'\b[a-zA-Z]{4,}\b', orig_title.lower())
    stopwords = {'dengan', 'yang', 'untuk', 'pada', 'dari', 'bisa', 'akan', 'oleh', 'saja', 'juga', 'dalam', 'atau', 'video', 'youtube', 'clip', 'clipper'}
    custom_tags = []
    for w in words:
        if w not in stopwords and len(custom_tags) < 3:
            custom_tags.append(f"#{w}")

    default_tags = ["#fyp", "#viral", "#shorts", "#trending", "#yxgclip"]
    all_tags = " ".join(default_tags + custom_tags)

    return caption, all_tags


def fmt_time(seconds):
    """Format detik → MM:SS"""
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def fmt_srt_time(seconds):
    """Format detik → HH:MM:SS,mmm (format SRT)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    ms = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"


def parse_srt_time(time_str):
    """Parse SRT time HH:MM:SS,mmm → detik"""
    time_str = time_str.strip().replace(',', '.')
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def hex_to_ass_color(hex_str):
    """Konversi warna HEX #RRGGBB ke format ASS &H00BBGGRR"""
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 6:
        r = hex_str[0:2]
        g = hex_str[2:4]
        b = hex_str[4:6]
        return f"&H00{b}{g}{r}"
    return "&H00FFFFFF"


def ass_to_hex_color(ass_str):
    """Konversi format warna ASS &H00BBGGRR ke HEX #RRGGBB"""
    if not ass_str:
        return "#FFFFFF"
    clean = ass_str.replace("&H", "")
    if len(clean) == 8:
        b = clean[2:4]
        g = clean[4:6]
        r = clean[6:8]
        return f"#{r}{g}{b}"
    elif len(clean) == 6:
        b = clean[0:2]
        g = clean[2:4]
        r = clean[4:6]
        return f"#{r}{g}{b}"
    return "#FFFFFF"


def parse_srt_content(content):
    """Parse string file SRT menjadi list of dict cue."""
    if not content:
        return []
    content = content.replace('\r\n', '\n').strip()
    if not content:
        return []
    blocks = content.split('\n\n')
    cues = []
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            idx = lines[0].strip()
            time_line = lines[1].strip()
            if ' --> ' not in time_line:
                found = False
                for idx_line, l in enumerate(lines):
                    if ' --> ' in l:
                        time_line = l.strip()
                        idx = lines[idx_line-1].strip() if idx_line > 0 else idx
                        lines = lines[idx_line:]
                        found = True
                        break
                if not found:
                    continue
            text = '\n'.join(lines[2:])
            cues.append({
                'index': idx,
                'time_line': time_line,
                'text': text
            })
    return cues


def build_srt_content(cues):
    """Reconstruct list cue kembali menjadi format string SRT."""
    blocks = []
    for cue in cues:
        idx = cue.get('index', '1')
        time_line = cue.get('time_line', '00:00:00,000 --> 00:00:00,000')
        text = cue.get('text', '').strip()
        blocks.append(f"{idx}\n{time_line}\n{text}")
    return '\n\n'.join(blocks) + '\n'


# ==============================================================================
# 5. CORE FUNCTIONS
# ==============================================================================

def get_metadata(url):
    """Mengambil seluruh metadata video."""
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android'],
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)

            raw_chapters = info.get('chapters', []) or []
            chapters = []
            for idx, ch in enumerate(raw_chapters):
                chapters.append({
                    'index': idx,
                    'title': ch.get('title', f"Bab {idx+1}"),
                    'start_time': ch.get('start_time', 0.0),
                    'end_time': ch.get('end_time', 0.0)
                })

            heatmap = info.get('heatmap') or []

            auto_subs = info.get('automatic_captions', {}) or {}
            manual_subs = info.get('subtitles', {}) or {}
            available_sub_langs = []
            for lang in ['id', 'en']:
                if lang in manual_subs or lang in auto_subs:
                    available_sub_langs.append(lang)

            return {
                'status': 'success',
                'title': info.get('title', 'Video Tanpa Judul'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'channel': info.get('uploader', 'Tidak Diketahui'),
                'id': info.get('id', ''),
                'chapters': chapters,
                'heatmap': heatmap,
                'sub_langs': available_sub_langs,
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


def parse_heatmap_peaks(heatmap_data, duration, max_clips=6, min_clip_dur=15, max_clip_dur=60):
    if not heatmap_data or not isinstance(heatmap_data, list):
        return []

    valid_data = []
    for seg in heatmap_data:
        if isinstance(seg, dict) and 'start_time' in seg and 'end_time' in seg and 'value' in seg:
            valid_data.append(seg)
    if not valid_data:
        return []

    sorted_vals = sorted([s['value'] for s in valid_data], reverse=True)
    threshold_idx = max(1, len(sorted_vals) // 4)
    threshold = sorted_vals[min(threshold_idx, len(sorted_vals)-1)]

    peaks = []
    current_peak = None
    for seg in valid_data:
        if seg['value'] >= threshold:
            if current_peak is None:
                current_peak = {
                    'start_time': seg['start_time'],
                    'end_time': seg['end_time'],
                    'max_value': seg['value']
                }
            else:
                current_peak['end_time'] = seg['end_time']
                current_peak['max_value'] = max(current_peak['max_value'], seg['value'])
        else:
            if current_peak is not None:
                peaks.append(current_peak)
                current_peak = None
    if current_peak is not None:
        peaks.append(current_peak)

    peaks.sort(key=lambda x: x['max_value'], reverse=True)
    peaks = peaks[:max_clips]

    result = []
    for i, peak in enumerate(peaks):
        dur = peak['end_time'] - peak['start_time']
        if dur < min_clip_dur:
            center = (peak['start_time'] + peak['end_time']) / 2
            peak['start_time'] = max(0, center - min_clip_dur / 2)
            peak['end_time'] = min(duration, center + min_clip_dur / 2)
        elif dur > max_clip_dur:
            peak['end_time'] = peak['start_time'] + max_clip_dur

        result.append({
            'title': f"🔥 Momen Populer #{i+1}",
            'start_time': round(peak['start_time'], 1),
            'end_time': round(peak['end_time'], 1),
            'source': 'heatmap',
            'score': round(peak['max_value'], 2)
        })

    result.sort(key=lambda x: x['start_time'])
    return result


def analyze_transcript_highlights(srt_path, duration, max_clips=4, window_sec=45, step_sec=10, min_clip_dur=20, max_clip_dur=60):
    if not srt_path or not os.path.exists(srt_path):
        return []
    try:
        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return []

    cues = parse_srt_content(content)
    if not cues or len(cues) < 3:
        return []

    timed_cues = []
    for cue in cues:
        parts = cue['time_line'].split(' --> ')
        if len(parts) != 2:
            continue
        try:
            start = parse_srt_time(parts[0])
            end = parse_srt_time(parts[1])
            text = cue['text'].replace('\n', ' ').strip()
            timed_cues.append({'start': start, 'end': end, 'text': text})
        except Exception:
            continue

    if not timed_cues:
        return []

    emotional_words = [
        "rahasia", "tips", "trik", "penting", "menarik", "lucu", "ngakak", "keren",
        "parah", "gokil", "anjir", "gila", "hebat", "kaget", "syok", "sukses",
        "gagal", "ternyata", "bohong", "jujur", "beneran", "serius", "mustahil",
        "luar biasa", "mantap", "gilaa", "wkwk", "hahaha", "haha", "astaga",
        "aduh", "wow", "yah", "eh", "nggak nyangka", "tidak mungkin", "mengejutkan",
        "kenapa", "bagaimana", "tahu gak", "pernah gak", "gawat", "bahaya",
        "shock", "kocak", "epic", "akhirnya", "sebenarnya", "percaya", "terbukti",
        "secret", "viral", "fail", "success", "shocking", "funny", "laugh",
        "hack", "amazing", "crazy", "insane", "omg", "wait", "seriously",
        "unbelievable", "no way", "finally", "actually", "believe", "truth",
        "unexpected", "surprise", "incredible", "legendary", "goat"
    ]

    video_end = timed_cues[-1]['end'] if timed_cues else duration

    window_scores = []
    pos = timed_cues[0]['start']

    while pos < video_end - window_sec * 0.4:
        w_end = pos + window_sec
        window_cues = [c for c in timed_cues if c['start'] >= pos and c['start'] < w_end]

        if len(window_cues) < 2:
            pos += step_sec
            continue

        full_text_lower = ' '.join(c['text'] for c in window_cues).lower()
        orig_text = ' '.join(c['text'] for c in window_cues)
        score = 0.0

        word_hits = sum(1 for w in emotional_words if w in full_text_lower)
        score += min(0.5, word_hits * 0.15)
        score += min(0.3, full_text_lower.count('?') * 0.1)
        score += min(0.3, full_text_lower.count('!') * 0.1)
        score += min(0.1, full_text_lower.count('...') * 0.03)

        time_span = window_cues[-1]['end'] - window_cues[0]['start']
        if time_span > 0:
            cues_per_sec = len(window_cues) / time_span
            score += min(0.3, cues_per_sec * 0.08)

        alpha_chars = [c for c in orig_text if c.isalpha()]
        if alpha_chars:
            upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            score += min(0.2, upper_ratio * 0.4)

        window_scores.append({
            'start': pos,
            'end': min(w_end, video_end),
            'score': score,
            'cue_count': len(window_cues)
        })
        pos += step_sec

    if not window_scores:
        return []

    window_scores.sort(key=lambda x: x['score'], reverse=True)

    selected = []
    for w in window_scores:
        if w['score'] < 0.1:
            continue
        is_dup = False
        for sel in selected:
            ov_s = max(w['start'], sel['start'])
            ov_e = min(w['end'], sel['end'])
            if ov_e > ov_s and (ov_e - ov_s) / window_sec > 0.4:
                is_dup = True
                break
        if not is_dup:
            selected.append(w)
        if len(selected) >= max_clips:
            break

    result = []
    for i, w in enumerate(selected):
        dur = w['end'] - w['start']
        if dur < min_clip_dur:
            center = (w['start'] + w['end']) / 2
            w['start'] = max(0, center - min_clip_dur / 2)
            w['end'] = min(duration, center + min_clip_dur / 2)
        elif dur > max_clip_dur:
            w['end'] = w['start'] + max_clip_dur
        result.append({
            'title': f"\U0001f4ac Momen Viral #{i + 1}",
            'start_time': round(w['start'], 1),
            'end_time': round(w['end'], 1),
            'source': 'transcript',
            'score': round(w['score'], 2)
        })

    result.sort(key=lambda x: x['start_time'])
    return result


def analyze_audio_energy(url, video_id, duration, max_clips=4, min_clip_dur=20, max_clip_dur=60):
    if duration > 2400:
        return []

    base_audio_path = os.path.join(DOWNLOADS_DIR, f"audio_anl_{video_id}")

    try:
        for old_f in glob.glob(base_audio_path + '.*'):
            try:
                os.remove(old_f)
            except Exception:
                pass

        ydl_opts = {
            'format': 'worstaudio/bestaudio',
            'outtmpl': base_audio_path + '.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        downloaded = glob.glob(base_audio_path + '.*')
        if not downloaded:
            return []
        audio_path = downloaded[0]

        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-ar", "8000", "-ac", "1",
            "-f", "f32le", "pipe:1"
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)

        if proc.returncode != 0 or not proc.stdout:
            return []

        import struct
        interval_sec = 5
        sr = 8000
        samples_per_interval = sr * interval_sec
        bytes_per_interval = samples_per_interval * 4
        raw_data = proc.stdout

        rms_values = []
        for i in range(0, len(raw_data) - bytes_per_interval + 1, bytes_per_interval):
            chunk = raw_data[i:i + bytes_per_interval]
            n = len(chunk) // 4
            if n == 0:
                continue
            samples = struct.unpack(f'{n}f', chunk[:n * 4])
            rms = (sum(s * s for s in samples) / n) ** 0.5
            rms_values.append(rms)

        if not rms_values or len(rms_values) < 6:
            return []

        min_rms = min(rms_values)
        max_rms = max(rms_values)
        rms_range = max_rms - min_rms
        if rms_range < 0.005:
            return []
        norm = [(v - min_rms) / rms_range for v in rms_values]

        win_intervals = max(3, min(12, len(norm) // 4))
        step_intervals = max(1, win_intervals // 3)

        window_scores = []
        for i in range(0, len(norm) - win_intervals + 1, step_intervals):
            window = norm[i:i + win_intervals]
            avg_energy = sum(window) / len(window)
            mean_w = avg_energy
            variance = sum((v - mean_w) ** 2 for v in window) / len(window)
            combined = avg_energy * 0.55 + min(0.45, variance * 3.0)
            window_scores.append({
                'start': float(i * interval_sec),
                'end': float((i + win_intervals) * interval_sec),
                'score': combined,
                'avg_energy': avg_energy
            })

        if not window_scores:
            return []

        window_scores.sort(key=lambda x: x['score'], reverse=True)

        win_dur = win_intervals * interval_sec
        selected = []
        for w in window_scores:
            if w['avg_energy'] < 0.25:
                continue
            is_dup = False
            for sel in selected:
                ov_s = max(w['start'], sel['start'])
                ov_e = min(w['end'], sel['end'])
                if ov_e > ov_s and (ov_e - ov_s) / win_dur > 0.4:
                    is_dup = True
                    break
            if not is_dup:
                selected.append(w)
            if len(selected) >= max_clips:
                break

        result_clips = []
        for i, w in enumerate(selected):
            start = min(w['start'], max(0.0, duration - min_clip_dur))
            end = min(w['end'], duration)
            dur = end - start
            if dur < min_clip_dur:
                center = (start + end) / 2
                start = max(0, center - min_clip_dur / 2)
                end = min(duration, center + min_clip_dur / 2)
            elif dur > max_clip_dur:
                end = start + max_clip_dur
            result_clips.append({
                'title': f"\U0001f3b5 Momen Energi #{i + 1}",
                'start_time': round(start, 1),
                'end_time': round(end, 1),
                'source': 'audio_energy',
                'score': round(w['score'], 2)
            })

        result_clips.sort(key=lambda x: x['start_time'])
        return result_clips

    except Exception:
        return []
    finally:
        for f in glob.glob(base_audio_path + '.*'):
            try:
                os.remove(f)
            except Exception:
                pass


def analyze_with_gemini(srt_content, duration, api_key, model="gemini-1.5-flash"):
    import requests as _req
    import json as _json

    if not api_key or not srt_content:
        return []

    transcript_trimmed = srt_content[:14000]

    prompt = f"""Kamu adalah expert analisis konten YouTube yang sangat berpengalaman.
Diberikan transcript/subtitle dari sebuah video YouTube, tugasmu adalah mengidentifikasi
TOP 6 momen yang paling MENARIK, VIRAL, atau BERNILAI untuk dijadikan clip pendek.

Kriteria momen yang baik untuk di-clip:
- Punchline atau humor yang sangat lucu dan mengejutkan
- Fakta mengejutkan, plot twist, atau revelasi penting
- Puncak emosi (marah, haru, kagum, kaget yang autentik)
- Insight atau penjelasan yang sangat valuable dan actionable
- Konflik, perdebatan, atau drama yang menarik perhatian
- Momen "hook" yang membuat penonton ingin share

Aturan WAJIB:
- Setiap clip minimal 20 detik, maksimal {min(int(duration), 90)} detik
- Timestamps harus dalam format angka detik (contoh: 45.0, tidak "0:45")
- JANGAN melampaui durasi video: {int(duration)} detik
- Jika dua momen sangat berdekatan, ambil yang lebih menarik saja
- title maksimal 50 karakter, reason maksimal 120 karakter
- WAJIB: Sebar clip dari AWAL hingga AKHIR video! Minimal 1 clip dari:
  * Bagian AWAL (0 - {int(duration/3)} detik)
  * Bagian TENGAH ({int(duration/3)} - {int(duration*2/3)} detik)
  * Bagian AKHIR ({int(duration*2/3)} - {int(duration)} detik)
- JANGAN memilih semua clip dari satu bagian video saja

Kembalikan HANYA JSON array berikut (tanpa teks, komentar, atau markdown apapun di luar array):
[
  {{
    "start_time": 45.0,
    "end_time": 105.0,
    "title": "Judul singkat momen",
    "reason": "Alasan momen ini viral atau penting untuk penonton"
  }}
]

Transcript video (durasi total: {int(duration)} detik):
{transcript_trimmed}"""

    url_endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
        f":generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 1024,
        }
    }

    try:
        resp = _req.post(url_endpoint, json=payload, timeout=45)
        resp.raise_for_status()
        resp_data = resp.json()

        raw_text = resp_data['candidates'][0]['content']['parts'][0]['text'].strip()

        json_start = raw_text.find('[')
        json_end = raw_text.rfind(']') + 1
        if json_start == -1 or json_end == 0:
            return []

        clips_raw = _json.loads(raw_text[json_start:json_end])
        if not isinstance(clips_raw, list):
            return []

        result_clips = []
        for i, c in enumerate(clips_raw[:6]):
            try:
                start = max(0.0, float(c.get('start_time', 0)))
                end = min(float(duration), float(c.get('end_time', start + 30)))
                if end - start < 10:
                    continue
                result_clips.append({
                    'title': f"\U0001f916 {str(c.get('title', f'AI Clip #{i+1}'))[:50]}",
                    'start_time': round(start, 1),
                    'end_time': round(end, 1),
                    'source': 'ai_gemini',
                    'score': 0.95,
                    'ai_reason': str(c.get('reason', ''))[:120]
                })
            except (ValueError, TypeError):
                continue

        result_clips.sort(key=lambda x: x['start_time'])
        return result_clips

    except Exception:
        return []


def analyze_clip_transcript(srt_path, start_time, end_time):
    if not srt_path or not os.path.exists(srt_path):
        return {"keywords_found": [], "hook_score": 0.0, "text_snippet": ""}

    try:
        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return {"keywords_found": [], "hook_score": 0.0, "text_snippet": ""}

    blocks = content.strip().split('\n\n')
    clip_texts = []

    hooks_indo = ["rahasia", "tips", "trik", "penting", "menarik", "lucu", "ngakak", "keren", "parah", "gokil", "anjir", "gila", "hebat", "kaget", "syok", "sukses", "gagal", "tahu gak", "pernah gak", "bagaimana", "kenapa"]
    hooks_eng = ["secret", "viral", "fail", "success", "shocking", "funny", "laugh", "hack", "tips", "wow", "amazing", "crazy", "did you know", "why", "how to"]

    keywords_found = []

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        time_line_idx = -1
        for li, line in enumerate(lines):
            if ' --> ' in line:
                time_line_idx = li
                break
        if time_line_idx < 0:
            continue

        time_line = lines[time_line_idx]
        parts = time_line.split(' --> ')
        if len(parts) != 2:
            continue

        try:
            sub_start = parse_srt_time(parts[0])
            sub_end = parse_srt_time(parts[1])
        except Exception:
            continue

        if sub_end <= start_time or sub_start >= end_time:
            continue

        text = ' '.join(lines[time_line_idx + 1:])
        clip_texts.append(text)

        text_lower = text.lower()
        for kw in hooks_indo + hooks_eng:
            if kw in text_lower and kw not in keywords_found:
                keywords_found.append(kw)

    full_text = " ".join(clip_texts)
    hook_score = min(1.0, len(keywords_found) * 0.15)

    if "?" in full_text:
        hook_score = min(1.0, hook_score + 0.1)
    if "!" in full_text:
        hook_score = min(1.0, hook_score + 0.1)

    words = full_text.split()
    snippet = " ".join(words[:12]) + ("..." if len(words) > 12 else "")

    return {
        "keywords_found": keywords_found,
        "hook_score": hook_score,
        "text_snippet": snippet
    }


def calculate_viral_score(clip, srt_path=None):
    base_scores = {
        'ai_gemini': 0.92,
        'heatmap': 0.75,
        'chapter': 0.65,
        'transcript': 0.60,
        'audio_energy': 0.55,
        'auto': 0.40
    }
    score = base_scores.get(clip['source'], 0.50)
    reasons = []

    if clip['source'] == 'ai_gemini':
        reasons.append("\U0001f916 Momen diidentifikasi oleh Gemini AI secara kontekstual")
        ai_reason = clip.get('ai_reason', '')
        if ai_reason:
            reasons.append(f"\U0001f4a1 {ai_reason}")
    elif clip['source'] == 'heatmap':
        score += min(0.15, clip.get('score', 0.0) * 0.1)
        reasons.append("🔥 Momen paling sering diputar penonton (Most Replayed)")
    elif clip['source'] == 'chapter':
        reasons.append("📖 Bagian dari bab/chapter video yang terstruktur")
    elif clip['source'] == 'transcript':
        score += min(0.10, clip.get('score', 0.0) * 0.1)
        reasons.append("💬 Terdeteksi lonjakan kata emosional & kecepatan bicara tinggi")
    elif clip['source'] == 'audio_energy':
        score += min(0.10, clip.get('score', 0.0) * 0.1)
        reasons.append("🎵 Terdeteksi zona energi audio paling ramai/dinamis")
    else:
        reasons.append("✂️ Pembagian segmen otomatis durasi ideal")

    if srt_path and os.path.exists(srt_path):
        analysis = analyze_clip_transcript(srt_path, clip['start_time'], clip['end_time'])
        hook_score = analysis['hook_score']
        score += hook_score * 0.15

        if analysis['keywords_found']:
            kws = ", ".join(analysis['keywords_found'][:3])
            reasons.append(f"💬 Mengandung kata kunci bernilai viral ({kws})")
        if "?" in analysis['text_snippet']:
            reasons.append("❓ Terdapat kalimat tanya pemicu rasa ingin tahu")

    final_score = min(0.99, max(0.20, score))
    return int(round(final_score * 100)), reasons


def detect_highlights(metadata, target_dur=60, srt_path=None, url=None,
                      gemini_api_key=None, gemini_model="gemini-1.5-flash"):
    clips = []
    duration = metadata['duration']
    video_id = metadata.get('id', '')

    if gemini_api_key and srt_path and os.path.exists(srt_path):
        try:
            with open(srt_path, 'r', encoding='utf-8', errors='ignore') as _f:
                srt_for_ai = _f.read()
            ai_clips = analyze_with_gemini(srt_for_ai, duration, gemini_api_key, gemini_model)
            clips.extend(ai_clips)
        except Exception:
            pass

    for ch in metadata.get('chapters', []):
        dur = ch['end_time'] - ch['start_time']
        if dur > 3:
            clips.append({
                'title': f"📖 {ch['title']}",
                'start_time': ch['start_time'],
                'end_time': ch['end_time'],
                'source': 'chapter',
                'score': 0.8
            })

    heatmap_clips = parse_heatmap_peaks(metadata.get('heatmap', []), duration, max_clip_dur=target_dur)

    for hc in heatmap_clips:
        is_duplicate = False
        for existing in clips:
            overlap_start = max(hc['start_time'], existing['start_time'])
            overlap_end = min(hc['end_time'], existing['end_time'])
            if overlap_end > overlap_start:
                overlap_dur = overlap_end - overlap_start
                hc_dur = hc['end_time'] - hc['start_time']
                if overlap_dur / hc_dur > 0.5:
                    is_duplicate = True
                    break
        if not is_duplicate:
            clips.append(hc)

    if srt_path:
        gaps = _find_coverage_gaps(clips, duration, min_gap_sec=max(60, duration * 0.2))
        if len(clips) < 3 or gaps:
            transcript_clips = analyze_transcript_highlights(
                srt_path, duration, max_clips=6, max_clip_dur=target_dur
            )
            for tc in transcript_clips:
                is_dup = False
                for ex in clips:
                    ov_s = max(tc['start_time'], ex['start_time'])
                    ov_e = min(tc['end_time'], ex['end_time'])
                    tc_dur = tc['end_time'] - tc['start_time']
                    if ov_e > ov_s and tc_dur > 0 and (ov_e - ov_s) / tc_dur > 0.4:
                        is_dup = True
                        break
                if not is_dup:
                    clips.append(tc)

    if url and video_id:
        gaps = _find_coverage_gaps(clips, duration, min_gap_sec=max(60, duration * 0.2))
        if len(clips) < 2 or gaps:
            audio_clips = analyze_audio_energy(
                url, video_id, duration, max_clips=6, max_clip_dur=target_dur
            )
            for ac in audio_clips:
                is_dup = False
                for ex in clips:
                    ov_s = max(ac['start_time'], ex['start_time'])
                    ov_e = min(ac['end_time'], ex['end_time'])
                    ac_dur = ac['end_time'] - ac['start_time']
                    if ov_e > ov_s and ac_dur > 0 and (ov_e - ov_s) / ac_dur > 0.4:
                        is_dup = True
                        break
                if not is_dup:
                    clips.append(ac)

    clips = _fill_coverage_gaps(clips, duration, target_dur)

    if not clips:
        clip_dur = target_dur
        pos = 0.0
        idx = 1
        while pos < duration:
            end = min(pos + clip_dur, duration)
            if end - pos >= 5:
                clips.append({
                    'title': f"✂️ Segment #{idx}",
                    'start_time': round(pos, 1),
                    'end_time': round(end, 1),
                    'source': 'auto',
                    'score': 0.5
                })
                idx += 1
            pos = end

    for clip in clips:
        score, reasons = calculate_viral_score(clip, srt_path)
        clip['viral_score'] = score
        clip['viral_reasons'] = reasons

    clips.sort(key=lambda x: x['start_time'])
    return _select_clips_with_coverage(clips, duration, max_clips=8)


def _find_coverage_gaps(clips, duration, min_gap_sec=60):
    if not clips:
        return [(0.0, duration)]

    sorted_clips = sorted(clips, key=lambda x: x['start_time'])
    gaps = []

    if sorted_clips[0]['start_time'] > min_gap_sec:
        gaps.append((0.0, sorted_clips[0]['start_time']))

    for i in range(len(sorted_clips) - 1):
        gap_start = sorted_clips[i]['end_time']
        gap_end = sorted_clips[i + 1]['start_time']
        if gap_end - gap_start > min_gap_sec:
            gaps.append((gap_start, gap_end))

    if duration - sorted_clips[-1]['end_time'] > min_gap_sec:
        gaps.append((sorted_clips[-1]['end_time'], duration))

    return gaps


def _fill_coverage_gaps(clips, duration, target_dur):
    if duration < 30:
        return clips

    third = duration / 3
    zones = [
        ('awal',   0.0,       third,       '⏮️ Pembuka Video'),
        ('tengah', third,     third * 2,   '🎯 Inti Video'),
        ('akhir',  third * 2, duration,    '🏁 Penutup Video'),
    ]

    result = list(clips)

    for zone_name, z_start, z_end, zone_label in zones:
        has_coverage = any(
            c['start_time'] < z_end and c['end_time'] > z_start
            for c in result
        )
        if has_coverage:
            continue

        center = (z_start + z_end) / 2
        clip_start = max(0.0, center - target_dur / 2)
        clip_end = min(duration, clip_start + target_dur)

        is_dup = False
        for ex in result:
            ov_s = max(clip_start, ex['start_time'])
            ov_e = min(clip_end, ex['end_time'])
            clip_d = clip_end - clip_start
            if ov_e > ov_s and clip_d > 0 and (ov_e - ov_s) / clip_d > 0.5:
                is_dup = True
                break

        if not is_dup and clip_end - clip_start >= 10:
            result.append({
                'title': f"✂️ {zone_label}",
                'start_time': round(clip_start, 1),
                'end_time': round(clip_end, 1),
                'source': 'auto',
                'score': 0.5
            })

    return result


def _select_clips_with_coverage(clips, duration, max_clips=8):
    if len(clips) <= max_clips:
        return clips

    third = duration / 3
    early  = [c for c in clips if c['start_time'] < third]
    middle = [c for c in clips if third <= c['start_time'] < third * 2]
    late   = [c for c in clips if c['start_time'] >= third * 2]

    selected = []
    quota_each = max(1, max_clips // 3)

    for zone_clips in [early, middle, late]:
        zone_sorted = sorted(
            zone_clips,
            key=lambda x: x.get('viral_score', x.get('score', 0)),
            reverse=True
        )
        selected.extend(zone_sorted[:quota_each])

    remaining_slots = max_clips - len(selected)
    if remaining_slots > 0:
        already_ids = set(id(c) for c in selected)
        leftover = sorted(
            [c for c in clips if id(c) not in already_ids],
            key=lambda x: x.get('viral_score', x.get('score', 0)),
            reverse=True
        )
        selected.extend(leftover[:remaining_slots])

    selected.sort(key=lambda x: x['start_time'])
    return selected


def convert_srt_to_ass(srt_path, ass_path, cfg):
    """Mengonversi berkas SRT ke ASS dengan gaya desain modern/viral."""
    if not srt_path or not os.path.exists(srt_path):
        return None

    try:
        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return None

    cues = parse_srt_content(content)
    if not cues:
        return None

    font_name = cfg.get('font_name', 'Arial')
    font_size = cfg.get('font_size', 20)
    primary_color = cfg.get('primary_color', '&H00FFFFFF')
    outline_color = cfg.get('outline_color', '&H00000000')
    back_color = cfg.get('back_color', '&H80000000')
    border_style = cfg.get('border_style', 1)
    bold = cfg.get('bold', False)
    alignment = cfg.get('alignment', 2)
    margin_v = cfg.get('margin_v', 25)
    preset = cfg.get('preset', 'Klasik (Kustom)')

    bold_val = "-1" if bold else "0"

    secondary_color = "&H0000FFFF"
    if preset == "🔥 Viral TikTok":
        font_name = "Impact"
        font_size = int(font_size * 1.3)
        primary_color = "&H0000FFFF"
        outline_color = "&H00000000"
        border_style = 1
        bold_val = "-1"
        alignment = 2
    elif preset == "🔥 Karaoke Highlight":
        font_name = "Arial Black"
        font_size = int(font_size * 1.2)
        primary_color = "&H00FFFFFF"
        outline_color = "&H00000000"
        border_style = 1
        bold_val = "-1"
        alignment = 2
    elif preset == "🔥 Karaoke Swipe (Gradual)":
        font_name = "Impact"
        font_size = int(font_size * 1.3)
        primary_color = "&H0000FFFF"
        secondary_color = "&H00FFFFFF"
        outline_color = "&H00000000"
        border_style = 1
        bold_val = "-1"
        alignment = 2
    elif preset == "🔥 Minimalis Modern":
        font_name = "Trebuchet MS"
        font_size = int(font_size * 1.1)
        primary_color = "&H00FFFFFF"
        outline_color = "&H00000000"
        border_style = 3
        back_color = "&H99000000"
        bold_val = "-1"
        alignment = 2

    is_portrait = cfg.get('format_type') == "Portrait (9:16)"
    play_res_y = "1138" if is_portrait else "360"
    play_res_x = "640"

    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {play_res_x}",
        f"PlayResY: {play_res_y}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]

    outline_size = 3 if border_style == 1 else 0
    shadow_size = 1 if border_style == 1 else 0

    if preset in ["🔥 Viral TikTok", "🔥 Karaoke Highlight", "🔥 Karaoke Swipe (Gradual)"]:
        outline_size = 4
        shadow_size = 1

    ass_lines.append(
        f"Style: Default,{font_name},{font_size},{primary_color},{secondary_color},{outline_color},{back_color},"
        f"{bold_val},0,0,0,100,100,0,0,{border_style},{outline_size},{shadow_size},{alignment},10,10,{margin_v},1"
    )
    ass_lines.extend([
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ])

    for cue in cues:
        time_line_parts = cue['time_line'].split(' --> ')
        if len(time_line_parts) != 2:
            continue

        def srt_to_ass_time(srt_t):
            parts = srt_t.strip().replace(',', '.').split(':')
            sec_parts = parts[2].split('.')
            ms = sec_parts[1][:2] if len(sec_parts) > 1 else '00'
            if len(ms) == 1: ms += '0'
            return f"{int(parts[0])}:{parts[1]}:{sec_parts[0]}.{ms}"

        try:
            start_ass = srt_to_ass_time(time_line_parts[0])
            end_ass = srt_to_ass_time(time_line_parts[1])
        except Exception:
            continue

        text = cue['text'].strip()

        if preset == "🔥 Viral TikTok":
            text = text.upper()
        elif preset == "🔥 Karaoke Highlight":
            text = text.upper()
            try:
                s_sec = parse_srt_time(time_line_parts[0])
                e_sec = parse_srt_time(time_line_parts[1])
                total_cs = int((e_sec - s_sec) * 100)
            except Exception:
                total_cs = 100
            words = text.split()
            if words:
                cs_per_word = max(10, total_cs // len(words))
                text = " ".join([f"{{\\k{cs_per_word}}}{w}" for w in words])
        elif preset == "🔥 Karaoke Swipe (Gradual)":
            text = text.upper()
            try:
                s_sec = parse_srt_time(time_line_parts[0])
                e_sec = parse_srt_time(time_line_parts[1])
                total_cs = int((e_sec - s_sec) * 100)
            except Exception:
                total_cs = 100
            words = text.split()
            if words:
                cs_per_word = max(10, total_cs // len(words))
                text = " ".join([f"{{\\kf{cs_per_word}}}{w}" for w in words])
        elif preset == "🔥 Minimalis Modern":
            text = text.upper()

        ass_lines.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}")

    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(ass_lines) + "\n")

    return ass_path


def download_subtitles(url, video_id, lang='id'):
    """Download subtitle otomatis dari YouTube dalam format SRT."""
    base_name = os.path.join(DOWNLOADS_DIR, f"{video_id}_subs")

    for old_file in glob.glob(f"{base_name}*.srt"):
        try: os.remove(old_file)
        except Exception: pass

    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': [lang],
        'outtmpl': base_name + '.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegSubtitlesConvertor',
            'format': 'srt',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    expected = f"{base_name}.{lang}.srt"
    if os.path.exists(expected):
        return expected

    srt_files = glob.glob(f"{base_name}*.srt")
    return srt_files[0] if srt_files else None


def extract_audio_from_clip(video_path, audio_output_path):
    if audio_output_path.endswith('.wav'):
        audio_output_path = audio_output_path.replace('.wav', '.ogg')
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "libvorbis", "-ar", "16000", "-ac", "1", "-q:a", "2",
        audio_output_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        audio_output_path = audio_output_path.replace('.ogg', '.wav')
        cmd_wav = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            audio_output_path
        ]
        result = subprocess.run(cmd_wav, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            return None
    return audio_output_path


def group_whisper_words_into_srt(segments, is_faster=False, max_words=5, max_chars=24, max_gap=0.35):
    srt_entries = []
    idx = 1
    all_words = []

    for seg in segments:
        if is_faster:
            words_list = getattr(seg, 'words', None)
            if words_list:
                for w in words_list:
                    all_words.append({'word': w.word, 'start': w.start, 'end': w.end})
        else:
            words_list = seg.get("words")
            if words_list:
                for w in words_list:
                    all_words.append({'word': w.get("word", ""), 'start': w.get("start", 0.0), 'end': w.get("end", 0.0)})

    if not all_words:
        for seg in segments:
            if is_faster:
                start = fmt_srt_time(seg.start)
                end = fmt_srt_time(seg.end)
                text = seg.text.strip()
            else:
                start = fmt_srt_time(seg.get("start", 0))
                end = fmt_srt_time(seg.get("end", 0))
                text = seg.get("text", "").strip()
            if text:
                srt_entries.append(f"{idx}\n{start} --> {end}\n{text}")
                idx += 1
        return srt_entries

    current_words = []
    for word_dict in all_words:
        w_text = word_dict['word'].strip()
        if not w_text:
            continue
        w_start = word_dict['start']
        w_end = word_dict['end']

        if current_words:
            prev_word = current_words[-1]
            prev_text = prev_word['word']
            prev_end = prev_word['end']

            should_split = False
            if any(prev_text.endswith(p) for p in ['.', '?', '!']):
                should_split = True
            elif prev_text.endswith(',') and len(current_words) >= 2:
                should_split = True
            elif (w_start - prev_end) > max_gap:
                should_split = True
            elif len(current_words) >= max_words:
                should_split = True
            else:
                current_len = sum(len(w['word']) + 1 for w in current_words) + len(w_text)
                if current_len > max_chars:
                    should_split = True

            if should_split:
                start_t = fmt_srt_time(current_words[0]['start'])
                end_t = fmt_srt_time(current_words[-1]['end'])
                text = " ".join([w['word'] for w in current_words]).strip()
                if text:
                    srt_entries.append(f"{idx}\n{start_t} --> {end_t}\n{text}")
                    idx += 1
                current_words = []

        current_words.append({'word': w_text, 'start': w_start, 'end': w_end})

    if current_words:
        start_t = fmt_srt_time(current_words[0]['start'])
        end_t = fmt_srt_time(current_words[-1]['end'])
        text = " ".join([w['word'] for w in current_words]).strip()
        if text:
            srt_entries.append(f"{idx}\n{start_t} --> {end_t}\n{text}")

    return srt_entries


def generate_whisper_srt(video_path, srt_output_path, model_size="base", language=None):
    model = load_whisper_model(model_size)
    if model is None:
        return None

    audio_path = srt_output_path.replace('.srt', '.ogg')
    extracted = extract_audio_from_clip(video_path, audio_path)
    if not extracted:
        return None
    audio_path = extracted

    lang_code = language if language != "Auto-Detect" else None

    try:
        srt_entries = []
        if WHISPER_TYPE == 'faster':
            segments, info = model.transcribe(audio_path, beam_size=1, language=lang_code, word_timestamps=True, vad_filter=True)
            segments = list(segments)
            srt_entries = group_whisper_words_into_srt(segments, is_faster=True)
        elif WHISPER_TYPE == 'openai':
            transcribe_opts = {"word_timestamps": True, "temperature": 0.0}
            if lang_code:
                transcribe_opts['language'] = lang_code
            result = model.transcribe(audio_path, **transcribe_opts)
            segments = result.get("segments", [])
            srt_entries = group_whisper_words_into_srt(segments, is_faster=False)

        if not srt_entries:
            return None

        with open(srt_output_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(srt_entries) + '\n')

        return srt_output_path

    except Exception:
        return None
    finally:
        if os.path.exists(audio_path):
            try: os.remove(audio_path)
            except Exception: pass


def slice_srt(srt_path, start_sec, end_sec, output_path):
    if not srt_path or not os.path.exists(srt_path):
        return None

    try:
        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return None

    blocks = content.strip().split('\n\n')
    sliced = []
    idx = 1

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue

        time_line_idx = -1
        for li, line in enumerate(lines):
            if ' --> ' in line:
                time_line_idx = li
                break
        if time_line_idx < 0:
            continue

        time_line = lines[time_line_idx]
        parts = time_line.split(' --> ')
        if len(parts) != 2:
            continue

        sub_start = parse_srt_time(parts[0])
        sub_end = parse_srt_time(parts[1])

        if sub_end <= start_sec or sub_start >= end_sec:
            continue

        new_start = max(0.0, sub_start - start_sec)
        new_end = min(end_sec - start_sec, sub_end - start_sec)
        text = '\n'.join(lines[time_line_idx + 1:])

        if text.strip():
            sliced.append(f"{idx}\n{fmt_srt_time(new_start)} --> {fmt_srt_time(new_end)}\n{text}")
            idx += 1

    if not sliced:
        return None

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(sliced) + '\n')

    return output_path


def download_video_clip(url, start_sec, end_sec, video_id, quality="480p"):
    ts = f"{int(start_sec)}_{int(end_sec)}"
    output_path = os.path.join(DOWNLOADS_DIR, f"raw_{video_id}_{ts}.mp4")
    full_video_path = os.path.join(DOWNLOADS_DIR, f"full_{video_id}.mp4")

    if os.path.exists(output_path):
        try: os.remove(output_path)
        except Exception: pass

    fmt_map = {
        "360p": 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best',
        "480p": 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best',
        "720p": 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
        "1080p": 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
    }

    lock_path = full_video_path + ".lock"

    if os.path.exists(lock_path):
        import time
        try:
            mtime = os.path.getmtime(lock_path)
            if time.time() - mtime > 600:
                os.remove(lock_path)
        except Exception:
            pass

    if os.path.exists(lock_path):
        import time
        start_wait = time.time()
        with st.spinner("⏳ Menunggu unduhan video selesai di proses lain..."):
            while os.path.exists(lock_path):
                time.sleep(1)
                if time.time() - start_wait > 300:
                    break

    if not os.path.exists(full_video_path):
        try:
            with open(lock_path, "w") as f:
                f.write("locked")

            ydl_opts = {
                'format': fmt_map.get(quality, fmt_map["480p"]),
                'outtmpl': full_video_path,
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        finally:
            if os.path.exists(lock_path):
                try: os.remove(lock_path)
                except Exception: pass

    if not os.path.exists(full_video_path):
        raise Exception("Gagal mendownload video.")

    duration = end_sec - start_sec
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-i", full_video_path,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        output_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="ignore")
        raise Exception(f"FFmpeg gagal memotong video: {err}")

    return output_path


def process_video_effects(input_path, output_path, format_type,
                          logo_path=None, logo_position="Kanan Atas",
                          srt_path=None, font_name="Arial", font_size=20,
                          primary_color="&H00FFFFFF", outline_color="&H00000000",
                          border_style=1, bold=False, alignment=2, margin_v=25,
                          back_color="&H80000000",
                          # Portrait background fill options
                          portrait_fill="blur",          # 'blur', 'solid', 'gradient', 'image'
                          portrait_bg_color="#000000",   # solid / gradient start color
                          portrait_bg_color2="#1a1a2e",  # gradient end color
                          portrait_bg_image=None,        # path to background image
                          portrait_bg_video=None,        # path to satisfying background video
                          # Portrait overlay bar options
                          portrait_show_top_bar=True,
                          portrait_show_bottom_bar=True,
                          portrait_top_text="",          # e.g. video title
                          portrait_bottom_text="",       # e.g. hashtags
                          portrait_bar_color="#000000cc",
                          portrait_text_color="white",
                          portrait_text_size=20,
                          ):
    """
    Proses video dengan FFmpeg:
    - Portrait 9:16 dengan background fill (blur/solid/gradient/image)
    - Overlay info bar (judul, channel, hashtag)
    - Overlay logo/watermark
    - Burn subtitle SRT/ASS
    """
    is_portrait = format_type in ["Portrait Crop (9:16)", "Portrait Fit (9:16 Frame)"]
    is_fit = format_type == "Portrait Fit (9:16 Frame)"

    # Jika landscape tanpa efek apapun, salin langsung
    if not is_portrait and not logo_path and not srt_path:
        shutil.copy(input_path, output_path)
        return True

    cmd = ["ffmpeg", "-y", "-i", input_path]
    extra_inputs = []
    input_idx = 1  # 0 = input_path

    # Add background image input jika mode image
    if is_portrait and portrait_fill == "image" and portrait_bg_image and os.path.exists(portrait_bg_image):
        cmd.extend(["-i", portrait_bg_image])
        bg_img_idx = input_idx
        input_idx += 1
    else:
        bg_img_idx = None

    # Add background video input jika mode split_screen
    if is_portrait and portrait_fill == "split_screen" and portrait_bg_video and os.path.exists(portrait_bg_video):
        cmd.extend(["-stream_loop", "-1", "-i", portrait_bg_video])
        bg_vid_idx = input_idx
        input_idx += 1
    else:
        bg_vid_idx = None

    if logo_path and os.path.exists(logo_path):
        cmd.extend(["-i", logo_path])
        logo_idx = input_idx
        input_idx += 1
    else:
        logo_idx = None

    filter_parts = []
    current_layer = "[0:v]"

    if is_portrait:
        # ---- PORTRAIT 9:16 PROCESSING ----
        # Target: 720x1280 (9:16)
        target_w = 720
        target_h = 1280
        main_scale = f"scale={target_w}:-2" if is_fit else f"scale=-2:{target_h}"

        if portrait_fill == "blur":
            # Scale input to fill 720x1280, blur as background; overlay cropped 9:16 on top
            filter_parts.append(
                f"{current_layer}split=2[vid_main][vid_bg];"
                f"[vid_bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},boxblur=20:10[bg_blurred];"
                f"[vid_main]{main_scale}[vid_scaled];"
                f"[bg_blurred][vid_scaled]overlay=(W-w)/2:(H-h)/2[portrait_base]"
            )

        elif portrait_fill == "solid":
            # Solid color background
            r = int(portrait_bg_color.lstrip('#')[0:2], 16)
            g = int(portrait_bg_color.lstrip('#')[2:4], 16)
            b = int(portrait_bg_color.lstrip('#')[4:6], 16)
            filter_parts.append(
                f"color=c={portrait_bg_color.lstrip('#')}:size={target_w}x{target_h}:rate=30[bg_solid];"
                f"{current_layer}{main_scale}[vid_scaled];"
                f"[bg_solid][vid_scaled]overlay=(W-w)/2:(H-h)/2[portrait_base]"
            )

        elif portrait_fill == "gradient":
            # Gradient background using FFmpeg geq filter
            # Parse colors
            def hex_to_rgb(h):
                h = h.lstrip('#')
                return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            r1, g1, b1 = hex_to_rgb(portrait_bg_color)
            r2, g2, b2 = hex_to_rgb(portrait_bg_color2)
            filter_parts.append(
                f"color=black:size={target_w}x{target_h}:rate=30,"
                f"geq=r='{r1}+(({r2}-{r1})*Y/{target_h})':g='{g1}+(({g2}-{g1})*Y/{target_h})':b='{b1}+(({b2}-{b1})*Y/{target_h})'[bg_grad];"
                f"{current_layer}{main_scale}[vid_scaled];"
                f"[bg_grad][vid_scaled]overlay=(W-w)/2:(H-h)/2[portrait_base]"
            )

        elif portrait_fill == "image" and bg_img_idx is not None:
            filter_parts.append(
                f"[{bg_img_idx}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},boxblur=5:2[bg_img];"
                f"{current_layer}{main_scale}[vid_scaled];"
                f"[bg_img][vid_scaled]overlay=(W-w)/2:(H-h)/2[portrait_base]"
            )
        elif portrait_fill == "split_screen" and bg_vid_idx is not None:
            filter_parts.append(
                f"{current_layer}scale={target_w}:{target_h//2}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h//2}:(ow-iw)/2:(oh-ih)/2:color=black[top_vid];"
                f"[{bg_vid_idx}:v]scale={target_w}:{target_h//2}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h//2}[bot_vid];"
                f"[top_vid][bot_vid]vstack=inputs=2[portrait_base]"
            )
        else:
            # Fallback to blur
            filter_parts.append(
                f"{current_layer}split=2[vid_main][vid_bg];"
                f"[vid_bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},boxblur=20:10[bg_blurred];"
                f"[vid_main]{main_scale}[vid_scaled];"
                f"[bg_blurred][vid_scaled]overlay=(W-w)/2:(H-h)/2[portrait_base]"
            )

        current_layer = "[portrait_base]"

        # ---- TOP BAR OVERLAY (drawbox + drawtext) ----
        if portrait_show_top_bar and portrait_top_text:
            safe_top = portrait_top_text.replace("'", "\\'").replace(":", "\\:")[:60]
            filter_parts.append(
                f"{current_layer}"
                f"drawbox=x=0:y=0:w={target_w}:h=70:color=black@0.75:t=fill,"
                f"drawtext=text='{safe_top}':fontsize={portrait_text_size}:fontcolor=white:"
                f"x=(w-text_w)/2:y=20:box=0:shadowcolor=black@0.6:shadowx=1:shadowy=1"
                f"[with_top]"
            )
            current_layer = "[with_top]"

        # ---- BOTTOM BAR OVERLAY ----
        if portrait_show_bottom_bar and portrait_bottom_text:
            safe_bot = portrait_bottom_text.replace("'", "\\'").replace(":", "\\:")[:80]
            bar_y = target_h - 70
            filter_parts.append(
                f"{current_layer}"
                f"drawbox=x=0:y={bar_y}:w={target_w}:h=70:color=black@0.75:t=fill,"
                f"drawtext=text='{safe_bot}':fontsize={max(14, portrait_text_size - 4)}:fontcolor=white@0.85:"
                f"x=(w-text_w)/2:y={bar_y + 22}:box=0:shadowcolor=black@0.6:shadowx=1:shadowy=1"
                f"[with_bot]"
            )
            current_layer = "[with_bot]"

    else:
        # Landscape — no crop, pass through
        pass

    # ---- LOGO OVERLAY ----
    if logo_idx is not None:
        filter_parts.append(f"[{logo_idx}:v]scale=80:-1[logo_scaled]")
        pos_map = {
            "Kiri Atas": "15:15",
            "Kiri Bawah": "15:main_h-overlay_h-15",
            "Kanan Bawah": "main_w-overlay_w-15:main_h-overlay_h-15",
            "Kanan Atas": "main_w-overlay_w-15:15"
        }
        pos = pos_map.get(logo_position, pos_map["Kanan Atas"])
        filter_parts.append(f"{current_layer}[logo_scaled]overlay={pos}[logoed]")
        current_layer = "[logoed]"

    # ---- BURN SUBTITLES ----
    if srt_path and os.path.exists(srt_path):
        abs_srt = os.path.abspath(srt_path).replace("\\", "/").replace(":", "\\:")
        if srt_path.lower().endswith('.ass'):
            sub_filter = f"ass='{abs_srt}'"
        else:
            bold_val = "-1" if bold else "0"
            outline_val = 0 if border_style == 3 else 2
            shadow_val = 0 if border_style == 3 else 1
            sub_filter = (
                f"subtitles='{abs_srt}'"
                f":force_style='FontSize={font_size},FontName={font_name},"
                f"PrimaryColour={primary_color},OutlineColour={outline_color},BackColour={back_color},"
                f"BorderStyle={border_style},Bold={bold_val},Alignment={alignment},"
                f"Outline={outline_val},Shadow={shadow_val},MarginV={margin_v}'"
            )
        filter_parts.append(f"{current_layer}{sub_filter}[subtitled]")
        current_layer = "[subtitled]"

    if filter_parts:
        filter_str = "; ".join(filter_parts)
        cmd.extend(["-filter_complex", filter_str])
        cmd.extend(["-map", current_layer, "-map", "0:a?",
                    "-c:v", "libx264", "-c:a", "aac",
                    "-preset", "ultrafast", "-tune", "fastdecode",
                    "-crf", "28", "-threads", "0", "-shortest", output_path])
    else:
        cmd.extend(["-c", "copy", output_path])

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        error_msg = result.stderr.decode('utf-8', errors='ignore')
        raise Exception(f"FFmpeg Error: {error_msg}")

    return True


# ==============================================================================
# 6. UI HELPERS
# ==============================================================================

def render_step_indicator(current):
    steps = [("1", "Tempel Link"), ("2", "Pilih Clip"), ("3", "Ekspor")]
    html = []
    for i, (num, label) in enumerate(steps):
        sn = i + 1
        if sn < current:
            state, content = "done", "✓"
        elif sn == current:
            state, content = "active", num
        else:
            state, content = "pending", num
        html.append(f'<div class="step-node"><div class="step-circle {state}">{content}</div><div class="step-label {state}">{label}</div></div>')
        if i < len(steps) - 1:
            ls = "done" if sn < current else "pending"
            html.append(f'<div class="step-line {ls}"></div>')
    st.markdown(f'<div class="step-track">{"".join(html)}</div>', unsafe_allow_html=True)


def render_youtube_preview(video_id, start, end):
    url = f"https://www.youtube.com/embed/{video_id}?start={int(start)}&end={int(end)}&autoplay=0&rel=0"
    components.iframe(url, height=300)


def get_source_badge(source):
    badge_map = {
        'ai_gemini': ('badge-ai', '🤖 AI'),
        'heatmap': ('badge-heatmap', '🔥 Viral'),
        'chapter': ('badge-chapter', '📖 Chapter'),
        'transcript': ('badge-transcript', '💬 Transcript'),
        'audio_energy': ('badge-auto', '🎵 Audio'),
        'auto': ('badge-auto', '✂️ Auto'),
    }
    cls, label = badge_map.get(source, ('badge-auto', source))
    return f'<span class="clip-badge {cls}">{label}</span>'


# ==============================================================================
# 7. SIDEBAR
# ==============================================================================

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGO_PATH = os.path.join(_APP_DIR, "logo.png")

with st.sidebar:
    # Brand header
    if os.path.exists(_LOGO_PATH):
        col_l, col_r = st.columns([1, 3])
        with col_l:
            st.image(_LOGO_PATH, width=44)
        with col_r:
            st.markdown("""
            <div style="padding: 4px 0 10px; margin-bottom: 10px;">
                <div style="font-size: 1.1rem; font-weight: 800; color: #e8edf5; letter-spacing: -0.5px;">YXGClip</div>
                <div style="font-size: 0.58rem; color: #4f9cf9; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-top: 1px;">AUTO CLIPPER Studio</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('<div style="height: 1px; background: rgba(255,255,255,0.06); margin-top: -10px; margin-bottom: 12px;"></div>', unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="padding: 4px 0 10px; border-bottom: 1px solid rgba(255,255,255,0.06); margin-bottom: 12px;">
            <div style="font-size: 1.2rem; font-weight: 800; color: #e8edf5; letter-spacing: -0.6px;">YXGClip</div>
            <div style="font-size: 0.58rem; color: #4f9cf9; margin-top: 2px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase;">AUTO CLIPPER Studio</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">🎬 Format Output</div>', unsafe_allow_html=True)
    layout_choice = st.selectbox(
        "Rasio Video", 
        ["Portrait Fit (9:16 Bingkai) [Rekomendasi]", "Portrait Crop (9:16 Layar Penuh)", "Landscape Original (16:9)"],
        help="Portrait Fit menampilkan video asli tanpa dipotong sampingnya. Portrait Crop memotong samping video agar penuh."
    )
    if "Fit" in layout_choice:
        layout_format = "Portrait Fit (9:16 Frame)"
    elif "Crop" in layout_choice:
        layout_format = "Portrait Crop (9:16)"
    else:
        layout_format = "Landscape (16:9)"

    # ---- PORTRAIT BACKGROUND FILL (hanya muncul jika portrait) ----
    portrait_fill = "blur"
    portrait_bg_color = "#0d0d1a"
    portrait_bg_color2 = "#7c3aed"
    portrait_bg_image_path = None
    portrait_bg_video_path = None
    portrait_show_top = True
    portrait_show_bottom = True
    portrait_top_text_val = ""
    portrait_bottom_text_val = ""
    portrait_text_sz = 18

    if "Portrait" in layout_format:
        st.markdown('<div class="sidebar-section">🖼️ Background Portrait</div>', unsafe_allow_html=True)

        fill_labels = {
            "🎬 Blur Sinematik (dari video)": "blur",
            "⬛ Solid Color": "solid",
            "🎨 Gradient Custom": "gradient",
            "🖼️ Gambar / Wallpaper": "image",
            "🎮 Split Screen (Gameplay Video)": "split_screen",
        }
        fill_choice = st.selectbox(
            "Isi Area Atas & Bawah",
            list(fill_labels.keys()),
            index=0,
            help="Pilih background untuk area portrait di luar video."
        )
        portrait_fill = fill_labels[fill_choice]

        if portrait_fill == "solid":
            portrait_bg_color = st.color_picker("Warna Background", "#0d0d1a")

        elif portrait_fill == "gradient":
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                portrait_bg_color = st.color_picker("Warna Atas", "#0d0d1a")
            with col_g2:
                portrait_bg_color2 = st.color_picker("Warna Bawah", "#7c3aed")

        elif portrait_fill == "image":
            uploaded_bg = st.file_uploader("Upload Background Gambar", type=["jpg", "jpeg", "png", "webp"])
            if uploaded_bg:
                portrait_bg_image_path = os.path.join(DOWNLOADS_DIR, f"bg_{uploaded_bg.name}")
                with open(portrait_bg_image_path, "wb") as f:
                    f.write(uploaded_bg.getbuffer())

        elif portrait_fill == "split_screen":
            uploaded_bg_video = st.file_uploader("Upload Video Gameplay / Satisfying (MP4/MKV)", type=["mp4", "mkv", "mov", "avi"])
            if uploaded_bg_video:
                portrait_bg_video_path = os.path.join(DOWNLOADS_DIR, f"bg_vid_{uploaded_bg_video.name}")
                with open(portrait_bg_video_path, "wb") as f:
                    f.write(uploaded_bg_video.getbuffer())

        st.markdown('<div class="sidebar-section">📝 Overlay Info Bar</div>', unsafe_allow_html=True)

        portrait_show_top = st.toggle("Bar Atas (Judul/Channel)", value=True)
        portrait_show_bottom = st.toggle("Bar Bawah (Hashtag/Caption)", value=True)

        if portrait_show_top or portrait_show_bottom:
            portrait_text_sz = st.slider("Ukuran Teks Bar", min_value=12, max_value=30, value=18, step=2)

        portrait_top_text_val = ""
        portrait_bottom_text_val = ""

        st.caption("💡 Teks bar akan terisi otomatis dari judul video & hashtag setelah URL dianalisis. Kamu bisa edit per-klip di bawah nanti.")

    st.markdown('<div class="sidebar-section">⏱️ Durasi Klip</div>', unsafe_allow_html=True)
    target_clip_dur = st.slider(
        "Target Durasi (detik)",
        min_value=15, max_value=180, value=60, step=5,
        help="Durasi target pemotongan klip otomatis."
    )

    st.markdown('<div class="sidebar-section">🔥 Jumlah Klip Viral</div>', unsafe_allow_html=True)
    max_viral_clips = st.slider(
        "Jumlah Momen Dipotong",
        min_value=1, max_value=8, value=3, step=1,
        help="Jumlah klip teratas yang akan langsung dipotong otomatis."
    )

    st.markdown('<div class="sidebar-section">📐 Kualitas Video</div>', unsafe_allow_html=True)
    kualitas = st.selectbox("Resolusi", ["360p — Cepat", "480p — Standar", "720p — Tinggi", "1080p — Maksimal"], index=1)
    quality_map = {"360p — Cepat": "360p", "480p — Standar": "480p", "720p — Tinggi": "720p", "1080p — Maksimal": "1080p"}
    selected_quality = quality_map[kualitas]

    with st.expander("🖼️ Watermark / Logo"):
        uploaded_logo = st.file_uploader("Unggah Logo", type=["png", "jpg", "jpeg"])
        logo_pos = "Kanan Atas"
        saved_logo_path = None
        if uploaded_logo:
            logo_pos = st.selectbox("Posisi Logo", ["Kanan Atas", "Kiri Atas", "Kanan Bawah", "Kiri Bawah"])
            saved_logo_path = os.path.join(DOWNLOADS_DIR, f"logo_{uploaded_logo.name}")
            try:
                with open(saved_logo_path, "wb") as f:
                    f.write(uploaded_logo.getbuffer())
            except Exception:
                pass

    sub_font = "Arial"
    sub_size = 20
    sub_color_hex = "&H00FFFFFF"
    sub_outline_hex = "&H00000000"
    sub_preset = "Klasik (Kustom)"
    sub_source = "🎙️ Whisper AI (Lokal) — Akurat & Rapi"
    whisper_model_size = "small"
    transcribe_lang = "id"

    with st.expander("💬 Subtitle Otomatis"):
        enable_subtitle = st.toggle("Aktifkan Auto-Subtitle", value=True)
        if enable_subtitle:
            sub_source = st.selectbox(
                "Sumber Subtitel",
                ["🎙️ Whisper AI (Lokal) — Akurat & Rapi", "📺 YouTube Auto-Captions — Instan"],
                index=0,
            )

            if sub_source == "🎙️ Whisper AI (Lokal) — Akurat & Rapi":
                if check_whisper_available():
                    col_w1, col_w2 = st.columns(2)
                    with col_w1:
                        whisper_model_size = st.selectbox("Model Whisper", ["base", "small", "medium"], index=1)
                    with col_w2:
                        transcribe_lang = st.selectbox("Bahasa Video", ["id", "Auto-Detect", "en"], index=0)
                else:
                    st.warning("⚠️ Whisper tidak terdeteksi. Pakai YouTube Auto-Captions.")
                    sub_source = "📺 YouTube Auto-Captions — Instan"

            st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)
            sub_preset = st.selectbox(
                "Preset Gaya",
                ["Klasik (Kustom)", "🔥 Viral TikTok", "🔥 Karaoke Highlight", "🔥 Karaoke Swipe (Gradual)", "🔥 Minimalis Modern"],
                index=0,
            )

            if sub_preset == "Klasik (Kustom)":
                sub_font = st.selectbox("Font", ["Arial", "Arial Black", "Impact", "Comic Sans MS", "Trebuchet MS", "Verdana", "Courier New", "Georgia"])
                sub_size = st.slider("Ukuran Font", min_value=12, max_value=36, value=20, step=2)
                sub_color = st.selectbox("Warna Teks", ["Putih", "Kuning", "Sian (Biru Muda)", "Hijau", "Merah"])
                color_map = {"Putih": "FFFFFF", "Kuning": "00FFFF", "Sian (Biru Muda)": "FFFF00", "Hijau": "00FF00", "Merah": "0000FF"}
                sub_color_hex = f"&H00{color_map[sub_color]}"
                sub_outline = st.selectbox("Warna Outline", ["Hitam", "Abu-Abu", "Merah", "Biru"])
                outline_map = {"Hitam": "000000", "Abu-Abu": "808080", "Merah": "0000FF", "Biru": "FF0000"}
                sub_outline_hex = f"&H00{outline_map[sub_outline]}"
        else:
            enable_subtitle = False

    with st.expander("🤖 Integrasi Gemini AI"):
        if GEMINI_API_KEY:
            st.success("✅ Gemini AI aktif")
        else:
            st.info("ℹ️ Tambahkan GEMINI_API_KEY di secrets untuk analisis AI")

    st.markdown('<div style="text-align:center;padding:12px 0 4px;"><div style="font-size:0.62rem;color:#50586a;">Streamlit · yt-dlp · FFmpeg · v3.0</div></div>', unsafe_allow_html=True)


# ==============================================================================
# 8. MAIN CONTENT
# ==============================================================================

# ---- HERO ----
col_logo_l, col_logo_c, col_logo_r = st.columns([4.5, 1, 4.5])
with col_logo_c:
    if os.path.exists(_LOGO_PATH):
        st.image(_LOGO_PATH, use_container_width=True)

st.markdown("""
<div class="hero-wrap">
    <div class="hero-eyebrow">Gemini AI · FFmpeg · yt-dlp</div>
    <div class="hero-title">YouTube <em>Auto</em> Clipper</div>
    <div class="hero-sub">Tempel link → deteksi momen viral otomatis → portrait 9:16 → siap upload ke TikTok, Reels & Shorts</div>
</div>
""", unsafe_allow_html=True)

# ---- Step indicator ----
meta = st.session_state['video_metadata']
has_exports = bool(st.session_state.get('exported_files'))
if has_exports:
    current_step = 3
elif meta:
    current_step = 2
else:
    current_step = 1
render_step_indicator(current_step)


# ==========================================================
# STEP 1 — INPUT URL & ANALISIS
# ==========================================================

with st.container(border=True):
    st.markdown("""
    <div class="card-header" style="margin-bottom: 14px;">
        <div class="card-icon">🔗</div>
        <div>
            <div class="card-title">Tempel Link YouTube</div>
            <div class="card-desc">Deteksi otomatis momen viral · portrait 9:16 siap upload</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("url_input_form", border=False):
        col_url, col_go = st.columns([4, 1])
        with col_url:
            url_input = st.text_input("URL", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed")
        with col_go:
            btn_go = st.form_submit_button("🎬 Analisis & Potong", use_container_width=True)

# ---- Handle analisis ----
if btn_go and url_input.strip():
    if url_input != st.session_state['current_url']:
        st.session_state['video_metadata'] = None
        st.session_state['clips'] = []
        st.session_state['selected_clips'] = {}
        st.session_state['subtitle_path'] = None
        st.session_state['subtitle_lang'] = None
        st.session_state['exported_files'] = {}
        st.session_state['raw_video_files'] = {}
        st.session_state['clip_srts'] = {}
        st.session_state['clip_configs'] = {}
        st.session_state['clip_srt_cues'] = {}
        st.session_state['preview_clip_index'] = 0
        st.session_state['_clips_target_dur'] = None
        st.session_state['current_url'] = url_input

    with st.spinner("🔍 Menganalisis video & mendeteksi momen menarik…"):
        result = get_metadata(url_input)

    if result['status'] == 'error':
        st.error("❌ Gagal menganalisis video.")
        with st.expander("Detail Error"):
            st.code(result['message'])
    else:
        st.session_state['video_metadata'] = result

        srt_path = None
        if enable_subtitle and result.get('sub_langs'):
            lang = result['sub_langs'][0]
            with st.spinner(f"📝 Mengunduh subtitle otomatis ({lang.upper()})…"):
                try:
                    srt_path = download_subtitles(url_input, result['id'], lang)
                    st.session_state['subtitle_path'] = srt_path
                    st.session_state['subtitle_lang'] = lang
                except Exception:
                    st.session_state['subtitle_path'] = None

        with st.spinner("🧠 Menganalisis momen viral… 🤖 Gemini AI aktif"):
            clips = detect_highlights(
                result, target_clip_dur, srt_path, url=url_input,
                gemini_api_key=GEMINI_API_KEY,
                gemini_model=GEMINI_MODEL
            )
        st.session_state['clips'] = clips
        st.session_state['_clips_target_dur'] = target_clip_dur
        st.session_state['selected_clips'] = {i: True for i in range(len(clips))}

        sorted_clips_with_idx = sorted(list(enumerate(clips)), key=lambda x: x[1]['viral_score'], reverse=True)
        top_indices = [idx for idx, clip in sorted_clips_with_idx[:max_viral_clips]]

        n_selected = len(top_indices)
        if n_selected > 0:
            exported = {}
            progress = st.progress(0)
            status = st.empty()

            for step_i, clip_idx in enumerate(top_indices):
                clip = clips[clip_idx]
                clip_label = clip['title']
                status.markdown(f"**⏳ Clip {step_i+1}/{n_selected}:** {clip_label} — mengunduh video…")

                try:
                    raw_path = download_video_clip(
                        url_input, clip['start_time'], clip['end_time'],
                        result['id'], selected_quality
                    )

                    if not os.path.exists(raw_path):
                        continue

                    st.session_state['raw_video_files'][clip_idx] = raw_path

                    clip_srt = None
                    srt_out = os.path.join(DOWNLOADS_DIR, f"clip_{result['id']}_{int(clip['start_time'])}_{int(clip['end_time'])}.srt")

                    if enable_subtitle:
                        if sub_source == "📺 YouTube Auto-Captions — Instan" and st.session_state.get('subtitle_path'):
                            clip_srt = slice_srt(
                                st.session_state['subtitle_path'],
                                clip['start_time'], clip['end_time'], srt_out
                            )
                        if not clip_srt and check_whisper_available():
                            status.markdown(f"**🎙️ Clip {step_i+1}/{n_selected}:** {clip_label} — transkripsi Whisper…")
                            clip_srt = generate_whisper_srt(raw_path, srt_out, model_size=whisper_model_size, language=transcribe_lang)

                    srt_content = ""
                    if clip_srt and os.path.exists(clip_srt):
                        try:
                            with open(clip_srt, "r", encoding="utf-8") as sf:
                                srt_content = sf.read()
                        except Exception:
                            pass
                    st.session_state['clip_srts'][clip_idx] = srt_content
                    st.session_state['clip_srt_cues'][clip_idx] = parse_srt_content(srt_content)

                    # Build portrait overlay texts from video meta
                    auto_top_text = result.get('title', '')[:50] if portrait_show_top else ""
                    auto_bot_text = "#fyp #viral #shorts #trending #yxgclip" if portrait_show_bottom else ""

                    st.session_state['clip_configs'][clip_idx] = {
                        'font_name': sub_font,
                        'font_size': sub_size,
                        'primary_color': sub_color_hex,
                        'outline_color': sub_outline_hex,
                        'border_style': 1,
                        'bold': False,
                        'alignment': 2,
                        'margin_v': 25,
                        'back_color': '&H80000000',
                        'start_time': clip['start_time'],
                        'end_time': clip['end_time'],
                        'format_type': layout_format,
                        'logo_pos': logo_pos,
                        'use_logo': bool(uploaded_logo),
                        'logo_path': saved_logo_path,
                        'enable_subtitle': enable_subtitle,
                        'preset': sub_preset,
                        # Portrait config
                        'portrait_fill': portrait_fill,
                        'portrait_bg_color': portrait_bg_color,
                        'portrait_bg_color2': portrait_bg_color2,
                        'portrait_bg_image': portrait_bg_image_path,
                        'portrait_bg_video': portrait_bg_video_path,
                        'portrait_show_top': portrait_show_top,
                        'portrait_show_bottom': portrait_show_bottom,
                        'portrait_top_text': portrait_top_text_val or auto_top_text,
                        'portrait_bottom_text': portrait_bottom_text_val or auto_bot_text,
                        'portrait_text_size': portrait_text_sz,
                    }

                    status.markdown(f"**🎨 Clip {step_i+1}/{n_selected}:** {clip_label} — render efek & subtitle…")
                    final_path = os.path.join(DOWNLOADS_DIR, f"final_{result['id']}_{int(clip['start_time'])}_{int(clip['end_time'])}.mp4")

                    if os.path.exists(final_path):
                        try: os.remove(final_path)
                        except Exception: pass

                    sub_burn_path = clip_srt
                    if clip_srt and os.path.exists(clip_srt):
                        ass_out = srt_out.replace(".srt", ".ass")
                        convert_srt_to_ass(clip_srt, ass_out, st.session_state['clip_configs'][clip_idx])
                        sub_burn_path = ass_out

                    cfg_c = st.session_state['clip_configs'][clip_idx]
                    process_video_effects(
                        input_path=raw_path,
                        output_path=final_path,
                        format_type=layout_format,
                        logo_path=saved_logo_path if uploaded_logo else None,
                        logo_position=logo_pos,
                        srt_path=sub_burn_path,
                        font_name=sub_font,
                        font_size=sub_size,
                        primary_color=sub_color_hex,
                        outline_color=sub_outline_hex,
                        portrait_fill=cfg_c.get('portrait_fill', 'blur'),
                        portrait_bg_color=cfg_c.get('portrait_bg_color', '#000000'),
                        portrait_bg_color2=cfg_c.get('portrait_bg_color2', '#1a1a2e'),
                        portrait_bg_image=cfg_c.get('portrait_bg_image'),
                        portrait_bg_video=cfg_c.get('portrait_bg_video'),
                        portrait_show_top_bar=cfg_c.get('portrait_show_top', True),
                        portrait_show_bottom_bar=cfg_c.get('portrait_show_bottom', True),
                        portrait_top_text=cfg_c.get('portrait_top_text', ''),
                        portrait_bottom_text=cfg_c.get('portrait_bottom_text', ''),
                        portrait_text_size=cfg_c.get('portrait_text_size', 18),
                    )

                    if os.path.exists(final_path):
                        exported[clip_idx] = final_path

                except Exception as err:
                    st.error(f"❌ Error pada {clip_label}")
                    with st.expander("Detail Error"):
                        st.code(str(err))

                progress.progress((step_i + 1) / n_selected)

            progress.empty()
            status.empty()
            st.session_state['exported_files'] = exported

        st.rerun()

elif btn_go and not url_input.strip():
    st.warning("⚠️ Masukkan URL YouTube terlebih dahulu.")


# ==========================================================
# STEP 2 — CLIP LIST & PREVIEW
# ==========================================================

if st.session_state['video_metadata']:
    meta = st.session_state['video_metadata']
    cached_target = st.session_state.get('_clips_target_dur')

    if not st.session_state.get('clips') or cached_target != target_clip_dur:
        clips = detect_highlights(
            meta, target_clip_dur,
            st.session_state.get('subtitle_path')
        )
        st.session_state['clips'] = clips
        st.session_state['_clips_target_dur'] = target_clip_dur
    clips = st.session_state.get('clips', [])
    for i in range(len(clips)):
        if i not in st.session_state['selected_clips']:
            st.session_state['selected_clips'][i] = True

    # ---- Info Video ----
    sub_status = '✅ ' + (st.session_state.get('subtitle_lang') or '').upper() if st.session_state.get('subtitle_path') else '—'
    ai_status = '🤖 Aktif' if GEMINI_API_KEY else '—'
    fmt_badge = '📱 9:16' if "Portrait" in layout_format else '🖥️ 16:9'

    st.markdown(f"""
    <div class="glass-card">
        <div class="card-header">
            <div class="card-icon">📺</div>
            <div>
                <div class="card-title">Video Terdeteksi</div>
                <div class="card-desc">{meta['channel']}</div>
            </div>
        </div>
        <div class="meta-title-text">{meta['title']}</div>
        <div class="meta-grid">
            <div class="meta-item">
                <div class="meta-value">{fmt_time(meta['duration'])}</div>
                <div class="meta-key">Durasi</div>
            </div>
            <div class="meta-item">
                <div class="meta-value">{len(clips)}</div>
                <div class="meta-key">Clip Ditemukan</div>
            </div>
            <div class="meta-item">
                <div class="meta-value">{sub_status}</div>
                <div class="meta-key">Subtitle</div>
            </div>
            <div class="meta-item">
                <div class="meta-value">{fmt_badge}</div>
                <div class="meta-key">Format</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ==========================================================
    # STEP 3 — HASIL EKSPOR
    # ==========================================================
    if st.session_state.get('exported_files'):
        st.markdown('<div class="section-divider"><div class="section-divider-text">✅ Hasil Potongan Video</div></div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="glass-card" style="border-color: rgba(16,185,129,0.25); background: linear-gradient(135deg, rgba(16,185,129,0.04) 0%, rgba(5,150,105,0.02) 100%);">
            <div class="card-header">
                <div class="card-icon" style="background: rgba(16,185,129,0.15); border-color: rgba(16,185,129,0.3);">✅</div>
                <div>
                    <div class="result-header">
                        <div class="result-dot"></div>
                        <div class="card-title" style="color: #34d399;">Hasil Potongan — Putar & Edit</div>
                    </div>
                    <div class="card-desc">Putar video hasil klip, edit subtitle/overlay/logo per klip, lalu unduh</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        for clip_idx, fpath in st.session_state['exported_files'].items():
            if not os.path.exists(fpath):
                continue

            clip = clips[clip_idx] if clip_idx < len(clips) else None
            clip_title = clip['title'] if clip else f"Clip #{clip_idx+1}"

            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:10px; margin: 20px 0 10px;">
                <div style="width:3px; height:20px; background: linear-gradient(135deg,#a855f7,#ec4899); border-radius:2px; flex-shrink:0;"></div>
                <div style="font-weight:700; font-size:0.95rem; color:#f1f5f9; font-family:'Space Grotesk',sans-serif;">🎬 {clip_title}</div>
                {get_source_badge(clip['source']) if clip else ''}
            </div>
            """, unsafe_allow_html=True)

            # Viral score
            if clip:
                is_ai = clip.get('source') == 'ai_gemini'
                vscore = clip.get('viral_score', 0)
                score_color = "#a855f7" if is_ai else ("#f43f5e" if vscore >= 75 else "#c084fc")
                ai_badge = '<span style="background:rgba(168,85,247,0.2);color:#c084fc;font-size:0.6rem;padding:2px 8px;border-radius:99px;font-weight:700;margin-left:6px;border:1px solid rgba(168,85,247,0.3);">🤖 AI</span>' if is_ai else ""

                reasons_html = ""
                if clip.get('viral_reasons'):
                    reasons_html = "<div style='margin-top: 8px;'>"
                    for reason in clip['viral_reasons']:
                        reasons_html += f"<div style='font-size:0.7rem; color:#64748b; line-height:1.6; padding-left:4px;'>• {reason}</div>"
                    reasons_html += "</div>"

                st.markdown(f"""
                <div class="viral-bar-wrap">
                    <div class="viral-bar-header">
                        <span class="viral-bar-label">⚡ Potensi Viral{ai_badge}</span>
                        <span class="viral-bar-score" style="color:{score_color};">🔥 {vscore}%</span>
                    </div>
                    <div class="viral-bar-track">
                        <div class="viral-bar-fill" style="width:{vscore}%;"></div>
                    </div>
                    {reasons_html}
                </div>
                """, unsafe_allow_html=True)

            # Video + Edit
            col_vid, col_edt = st.columns([2, 3])
            with col_vid:
                # Show portrait frame indicator if portrait
                if "Portrait" in layout_format:
                    st.markdown("""
                    <div class="fill-preview-tag">📱 Portrait 9:16</div>
                    """, unsafe_allow_html=True)

                with open(fpath, "rb") as vf:
                    video_data = vf.read()

                st.video(video_data)

                srt_str = st.session_state['clip_srts'].get(clip_idx, "")
                suggested_caption, suggested_tags = generate_social_suggestions(clip, meta, srt_str)

                import re as _re
                clean_filename = _re.sub(r'[^\w\s-]', '', suggested_caption)
                clean_filename = _re.sub(r'[-\s]+', '_', clean_filename).strip('_')
                if not clean_filename:
                    clean_filename = f"clipper_{meta['id']}_{clip_idx}"
                else:
                    clean_filename = clean_filename[:80]

                st.download_button(
                    label=f"📥 Unduh — {clip_title}",
                    data=video_data,
                    file_name=f"{clean_filename}.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                    key=f"dl_{clip_idx}"
                )

                st.markdown('<div style="margin-top:14px; margin-bottom:4px; font-size:0.78rem; font-weight:700; color:#a855f7;">📱 Caption & Hashtag:</div>', unsafe_allow_html=True)
                st.text_area("Caption", value=suggested_caption, key=f"caption_{clip_idx}", height=60, label_visibility="collapsed")
                st.text_input("Hashtag", value=suggested_tags, key=f"tags_{clip_idx}", label_visibility="collapsed")

            with col_edt:
                with st.expander(f"✏️ Edit Klip & Konfigurasi", expanded=False):
                    if clip_idx not in st.session_state['clip_configs']:
                        st.session_state['clip_configs'][clip_idx] = {
                            'font_name': sub_font, 'font_size': sub_size,
                            'primary_color': sub_color_hex, 'outline_color': sub_outline_hex,
                            'border_style': 1, 'bold': False, 'alignment': 2, 'margin_v': 25,
                            'back_color': '&H80000000',
                            'start_time': clip['start_time'] if clip else 0.0,
                            'end_time': clip['end_time'] if clip else 10.0,
                            'format_type': layout_format, 'logo_pos': logo_pos,
                            'use_logo': bool(uploaded_logo), 'logo_path': saved_logo_path,
                            'enable_subtitle': enable_subtitle, 'preset': sub_preset,
                            'portrait_fill': portrait_fill, 'portrait_bg_color': portrait_bg_color,
                            'portrait_bg_color2': portrait_bg_color2, 'portrait_bg_image': portrait_bg_image_path,
                            'portrait_show_top': portrait_show_top, 'portrait_show_bottom': portrait_show_bottom,
                            'portrait_top_text': meta.get('title', '')[:50] if portrait_show_top else "",
                            'portrait_bottom_text': "#fyp #viral #shorts #yxgclip" if portrait_show_bottom else "",
                            'portrait_text_size': portrait_text_sz,
                        }
                    cfg = st.session_state['clip_configs'][clip_idx]
                    srt_str = st.session_state['clip_srts'].get(clip_idx, "")

                    tab_sub, tab_style, tab_portrait = st.tabs(["📝 Subtitle", "🎨 Desain & Waktu", "📱 Portrait Overlay"])

                    # Tab Subtitle
                    with tab_sub:
                        if clip_idx not in st.session_state['clip_srt_cues']:
                            st.session_state['clip_srt_cues'][clip_idx] = parse_srt_content(srt_str)

                        cues = st.session_state['clip_srt_cues'][clip_idx]
                        edited_cues = []
                        if cues:
                            st.caption("Edit teks & waktu per baris:")
                            for i_cue, cue in enumerate(cues):
                                col_t, col_inp, col_del = st.columns([2, 4, 1])
                                with col_t:
                                    new_time = st.text_input(f"Waktu {cue['index']}", value=cue['time_line'], key=f"srt_time_{clip_idx}_{i_cue}", label_visibility="collapsed")
                                with col_inp:
                                    new_text = st.text_input(f"Baris {cue['index']}", value=cue['text'], key=f"srt_text_{clip_idx}_{i_cue}", label_visibility="collapsed")
                                with col_del:
                                    if st.button("❌", key=f"srt_del_{clip_idx}_{i_cue}"):
                                        st.session_state['clip_srt_cues'][clip_idx].pop(i_cue)
                                        for idx2, c2 in enumerate(st.session_state['clip_srt_cues'][clip_idx]):
                                            c2['index'] = str(idx2 + 1)
                                        st.rerun()
                                cue['time_line'] = new_time
                                cue['text'] = new_text
                                edited_cues.append(cue)

                        if st.button("➕ Tambah Baris", key=f"add_cue_btn_{clip_idx}", use_container_width=True):
                            last_end = "00:00:00,000"
                            if cues:
                                tparts = cues[-1]['time_line'].split(' --> ')
                                if len(tparts) == 2:
                                    last_end = tparts[1]
                            try:
                                start_sec = parse_srt_time(last_end)
                            except Exception:
                                start_sec = 0.0
                            end_sec = start_sec + 3.0
                            st.session_state['clip_srt_cues'][clip_idx].append({
                                'index': str(len(cues) + 1),
                                'time_line': f"{fmt_srt_time(start_sec)} --> {fmt_srt_time(end_sec)}",
                                'text': 'Subtitle baru'
                            })
                            st.rerun()

                        with st.expander("📝 Edit Raw SRT"):
                            current_srt_val = build_srt_content(cues) if cues else srt_str
                            raw_srt_edited = st.text_area("Konten SRT", value=current_srt_val, key=f"srt_raw_{clip_idx}", height=140, label_visibility="collapsed")
                            if raw_srt_edited != current_srt_val:
                                st.session_state['clip_srt_cues'][clip_idx] = parse_srt_content(raw_srt_edited)
                                st.rerun()

                    # Tab Desain & Waktu
                    with tab_style:
                        col_cfg_l, col_cfg_r = st.columns(2)
                        with col_cfg_l:
                            edit_options = ["Portrait Fit (9:16 Bingkai) [Rekomendasi]", "Portrait Crop (9:16 Layar Penuh)", "Landscape Original (16:9)"]
                            edit_idx_sel = 0
                            if cfg.get('format_type') == "Portrait Crop (9:16)":
                                edit_idx_sel = 1
                            elif cfg.get('format_type') == "Landscape (16:9)":
                                edit_idx_sel = 2

                            edit_layout_choice = st.selectbox(
                                "Rasio Video", edit_options,
                                index=edit_idx_sel,
                                key=f"fmt_{clip_idx}"
                            )
                            if "Fit" in edit_layout_choice:
                                edit_format = "Portrait Fit (9:16 Frame)"
                            elif "Crop" in edit_layout_choice:
                                edit_format = "Portrait Crop (9:16)"
                            else:
                                edit_format = "Landscape (16:9)"
                            uploaded_clip_logo = st.file_uploader("Logo Klip", type=["png","jpg","jpeg"], key=f"logo_upload_{clip_idx}")
                            edit_logo_path = cfg.get('logo_path')
                            if uploaded_clip_logo:
                                edit_logo_path = os.path.join(DOWNLOADS_DIR, f"logo_{clip_idx}_{uploaded_clip_logo.name}")
                                try:
                                    with open(edit_logo_path, "wb") as f:
                                        f.write(uploaded_clip_logo.getbuffer())
                                except Exception:
                                    pass

                            edit_use_logo = False
                            edit_logo_pos = cfg.get('logo_pos', 'Kanan Atas')
                            logo_to_use = None
                            if edit_logo_path and os.path.exists(edit_logo_path):
                                logo_to_use = edit_logo_path
                            elif saved_logo_path and os.path.exists(saved_logo_path):
                                logo_to_use = saved_logo_path
                            if logo_to_use:
                                edit_use_logo = st.checkbox("Gunakan Watermark", value=cfg.get('use_logo', True), key=f"use_logo_{clip_idx}")
                                if edit_use_logo:
                                    edit_logo_pos = st.selectbox("Posisi", ["Kanan Atas","Kiri Atas","Kanan Bawah","Kiri Bawah"],
                                                                  index=["Kanan Atas","Kiri Atas","Kanan Bawah","Kiri Bawah"].index(cfg.get('logo_pos', 'Kanan Atas')),
                                                                  key=f"logo_pos_{clip_idx}")
                                    edit_logo_path = logo_to_use
                            edit_enable_sub = st.checkbox("Aktifkan Subtitle", value=cfg['enable_subtitle'], key=f"en_sub_{clip_idx}")

                        with col_cfg_r:
                            edit_start_time = st.number_input("Waktu Mulai (detik)", min_value=0.0, max_value=float(meta['duration']), value=float(cfg['start_time']), step=0.5, format="%.1f", key=f"start_t_{clip_idx}")
                            edit_end_time = st.number_input("Waktu Selesai (detik)", min_value=0.1, max_value=float(meta['duration']), value=float(cfg['end_time']), step=0.5, format="%.1f", key=f"end_t_{clip_idx}")

                        if edit_enable_sub:
                            edit_preset = st.selectbox(
                                "Preset Gaya Subtitle",
                                ["Klasik (Kustom)", "🔥 Viral TikTok", "🔥 Karaoke Highlight", "🔥 Karaoke Swipe (Gradual)", "🔥 Minimalis Modern"],
                                index=["Klasik (Kustom)", "🔥 Viral TikTok", "🔥 Karaoke Highlight", "🔥 Karaoke Swipe (Gradual)", "🔥 Minimalis Modern"].index(cfg.get('preset', 'Klasik (Kustom)')),
                                key=f"preset_{clip_idx}"
                            )
                            if edit_preset == "Klasik (Kustom)":
                                col_f1, col_f2 = st.columns(2)
                                with col_f1:
                                    avail_fonts = ["Arial", "Arial Black", "Impact", "Comic Sans MS", "Trebuchet MS", "Verdana", "Courier New", "Georgia"]
                                    f_idx = avail_fonts.index(cfg['font_name']) if cfg['font_name'] in avail_fonts else 0
                                    edit_font_name = st.selectbox("Font", avail_fonts, index=f_idx, key=f"font_name_{clip_idx}")
                                    custom_font = st.text_input("Font Kustom", value=cfg['font_name'] if cfg['font_name'] not in avail_fonts else "", key=f"cust_font_{clip_idx}", placeholder="Nama font sistem...")
                                    if custom_font.strip(): edit_font_name = custom_font.strip()
                                    edit_font_size = st.slider("Ukuran Font", 12, 48, int(cfg['font_size']), 2, key=f"font_size_{clip_idx}")
                                    edit_bold = st.checkbox("Bold", value=cfg['bold'], key=f"bold_{clip_idx}")
                                with col_f2:
                                    edit_style_type = st.selectbox("Gaya", ["Klasik (Outline)", "Modern (Kotak)"], index=0 if cfg['border_style'] == 1 else 1, key=f"border_style_{clip_idx}")
                                    edit_border_style = 1 if edit_style_type == "Klasik (Outline)" else 3
                                    align_opts = {"Bawah (Default)": 2, "Tengah": 10, "Atas": 6}
                                    edit_align_label = st.selectbox("Posisi Subtitle", list(align_opts.keys()), index=list(align_opts.values()).index(cfg['alignment']), key=f"align_{clip_idx}")
                                    edit_alignment = align_opts[edit_align_label]
                                    edit_margin_v = st.slider("Margin V", 5, 200, int(cfg['margin_v']), 5, key=f"margin_v_{clip_idx}")
                                col_c1, col_c2 = st.columns(2)
                                with col_c1:
                                    edit_hex_text = st.color_picker("Warna Teks", value=ass_to_hex_color(cfg['primary_color']), key=f"color_text_{clip_idx}")
                                    edit_primary_color = hex_to_ass_color(edit_hex_text)
                                with col_c2:
                                    color_label = "Warna Outline" if edit_border_style == 1 else "Warna Kotak"
                                    edit_hex_out = st.color_picker(color_label, value=ass_to_hex_color(cfg['outline_color'] if edit_border_style == 1 else cfg['back_color']), key=f"color_out_{clip_idx}")
                                    if edit_border_style == 1:
                                        edit_outline_color = hex_to_ass_color(edit_hex_out)
                                        edit_back_color = "&H80000000"
                                    else:
                                        edit_outline_color = "&H00000000"
                                        raw_ass = hex_to_ass_color(edit_hex_out)
                                        edit_back_color = raw_ass.replace("&H00", "&H80")
                            else:
                                edit_font_name = "Arial"; edit_font_size = 20; edit_bold = False
                                edit_border_style = 1; edit_alignment = 2; edit_margin_v = 25
                                edit_primary_color = "&H00FFFFFF"; edit_outline_color = "&H00000000"; edit_back_color = "&H80000000"
                        else:
                            edit_font_name = cfg['font_name']; edit_font_size = cfg['font_size']; edit_bold = cfg['bold']
                            edit_border_style = cfg['border_style']; edit_alignment = cfg['alignment']; edit_margin_v = cfg['margin_v']
                            edit_primary_color = cfg['primary_color']; edit_outline_color = cfg['outline_color']; edit_back_color = cfg['back_color']
                            edit_preset = "Klasik (Kustom)"

                    # Tab Portrait Overlay
                    with tab_portrait:
                        st.markdown('<div class="fill-preview-tag">📱 Konfigurasi Portrait 9:16</div>', unsafe_allow_html=True)

                        edit_fill_labels = {
                            "🎬 Blur Sinematik": "blur",
                            "⬛ Solid Color": "solid",
                            "🎨 Gradient Custom": "gradient",
                            "🖼️ Gambar": "image",
                            "🎮 Split Screen (Gameplay Video)": "split_screen",
                        }
                        current_fill_label = {v: k for k, v in edit_fill_labels.items()}.get(cfg.get('portrait_fill', 'blur'), "🎬 Blur Sinematik")
                        edit_fill_choice = st.selectbox("Background Fill", list(edit_fill_labels.keys()),
                                                         index=list(edit_fill_labels.keys()).index(current_fill_label),
                                                         key=f"pfill_{clip_idx}")
                        edit_portrait_fill = edit_fill_labels[edit_fill_choice]

                        edit_portrait_bg_color = cfg.get('portrait_bg_color', '#000000')
                        edit_portrait_bg_color2 = cfg.get('portrait_bg_color2', '#7c3aed')
                        edit_portrait_bg_image = cfg.get('portrait_bg_image')
                        edit_portrait_bg_video = cfg.get('portrait_bg_video')

                        if edit_portrait_fill == "solid":
                            edit_portrait_bg_color = st.color_picker("Warna Background", value=cfg.get('portrait_bg_color', '#000000'), key=f"pbgc_{clip_idx}")
                        elif edit_portrait_fill == "gradient":
                            col_pg1, col_pg2 = st.columns(2)
                            with col_pg1:
                                edit_portrait_bg_color = st.color_picker("Warna Atas", value=cfg.get('portrait_bg_color', '#0d0d1a'), key=f"pbgc1_{clip_idx}")
                            with col_pg2:
                                edit_portrait_bg_color2 = st.color_picker("Warna Bawah", value=cfg.get('portrait_bg_color2', '#7c3aed'), key=f"pbgc2_{clip_idx}")
                        elif edit_portrait_fill == "image":
                            up_bg2 = st.file_uploader("Background Gambar", type=["jpg","jpeg","png"], key=f"pbgi_{clip_idx}")
                            if up_bg2:
                                edit_portrait_bg_image = os.path.join(DOWNLOADS_DIR, f"bg_{clip_idx}_{up_bg2.name}")
                                with open(edit_portrait_bg_image, "wb") as f:
                                    f.write(up_bg2.getbuffer())
                        elif edit_portrait_fill == "split_screen":
                            up_bg_vid = st.file_uploader("Video Gameplay / Satisfying (MP4/MKV)", type=["mp4","mkv","mov","avi"], key=f"pbgv_{clip_idx}")
                            if up_bg_vid:
                                edit_portrait_bg_video = os.path.join(DOWNLOADS_DIR, f"bg_vid_{clip_idx}_{up_bg_vid.name}")
                                with open(edit_portrait_bg_video, "wb") as f:
                                    f.write(up_bg_vid.getbuffer())

                        st.markdown("**Overlay Bar**")
                        col_po1, col_po2 = st.columns(2)
                        with col_po1:
                            edit_show_top = st.checkbox("Bar Atas", value=cfg.get('portrait_show_top', True), key=f"pst_{clip_idx}")
                        with col_po2:
                            edit_show_bottom = st.checkbox("Bar Bawah", value=cfg.get('portrait_show_bottom', True), key=f"psb_{clip_idx}")

                        edit_top_text = st.text_input("Teks Atas (Judul/Channel)", value=cfg.get('portrait_top_text', meta.get('title', '')[:50]), key=f"ptt_{clip_idx}", max_chars=60)
                        edit_bottom_text = st.text_input("Teks Bawah (Hashtag/Caption)", value=cfg.get('portrait_bottom_text', '#fyp #viral #shorts'), key=f"ptb_{clip_idx}", max_chars=80)
                        edit_portrait_text_size = st.slider("Ukuran Teks Bar", 12, 30, int(cfg.get('portrait_text_size', 18)), 2, key=f"pts_{clip_idx}")

                    # Tombol Re-render
                    st.markdown('<div style="height: 8px;"></div>', unsafe_allow_html=True)
                    btn_re_render = st.button("🔄 Terapkan & Render Ulang", key=f"re_render_{clip_idx}", use_container_width=True)

                    if btn_re_render:
                        if edit_start_time >= edit_end_time:
                            st.error("❌ Waktu mulai harus lebih kecil dari waktu selesai.")
                        else:
                            final_srt_str = ""
                            if edit_enable_sub:
                                srt_cues = st.session_state['clip_srt_cues'].get(clip_idx, [])
                                if srt_cues:
                                    final_srt_str = build_srt_content(srt_cues)
                                else:
                                    final_srt_str = raw_srt_edited if 'raw_srt_edited' in dir() else ""

                            srt_out = os.path.join(DOWNLOADS_DIR, f"clip_{meta['id']}_{int(edit_start_time)}_{int(edit_end_time)}.srt")
                            if edit_enable_sub and final_srt_str.strip():
                                with open(srt_out, "w", encoding="utf-8") as sf:
                                    sf.write(final_srt_str)

                            timing_changed = (edit_start_time != cfg['start_time']) or (edit_end_time != cfg['end_time'])
                            raw_vid_path = st.session_state['raw_video_files'].get(clip_idx)

                            if timing_changed or not raw_vid_path or not os.path.exists(raw_vid_path):
                                with st.spinner("⏳ Mengunduh ulang rentang video baru..."):
                                    raw_vid_path = download_video_clip(url_input, edit_start_time, edit_end_time, meta['id'], selected_quality)
                                    st.session_state['raw_video_files'][clip_idx] = raw_vid_path

                                if edit_enable_sub and (not final_srt_str.strip() or timing_changed):
                                    clip_srt_res = None
                                    if sub_source == "📺 YouTube Auto-Captions — Instan" and st.session_state.get('subtitle_path'):
                                        clip_srt_res = slice_srt(st.session_state['subtitle_path'], edit_start_time, edit_end_time, srt_out)
                                    if not clip_srt_res and check_whisper_available():
                                        generate_whisper_srt(raw_vid_path, srt_out, model_size=whisper_model_size, language=transcribe_lang)
                                    if os.path.exists(srt_out):
                                        with open(srt_out, "r", encoding="utf-8") as sf:
                                            final_srt_str = sf.read()

                            st.session_state['clip_srts'][clip_idx] = final_srt_str
                            st.session_state['clip_srt_cues'][clip_idx] = parse_srt_content(final_srt_str)

                            final_path = os.path.join(DOWNLOADS_DIR, f"final_{meta['id']}_{int(edit_start_time)}_{int(edit_end_time)}.mp4")
                            if os.path.exists(final_path):
                                try: os.remove(final_path)
                                except Exception: pass

                            render_cfg = {
                                'font_name': edit_font_name, 'font_size': edit_font_size,
                                'primary_color': edit_primary_color, 'outline_color': edit_outline_color,
                                'border_style': edit_border_style, 'bold': edit_bold,
                                'alignment': edit_alignment, 'margin_v': edit_margin_v,
                                'back_color': edit_back_color, 'format_type': edit_format,
                                'preset': edit_preset,
                            }

                            sub_burn_path = srt_out if edit_enable_sub else None
                            if edit_enable_sub and srt_out and os.path.exists(srt_out):
                                ass_out = srt_out.replace(".srt", ".ass")
                                convert_srt_to_ass(srt_out, ass_out, render_cfg)
                                sub_burn_path = ass_out

                            with st.spinner("🎬 Memproses efek & render video..."):
                                process_video_effects(
                                    input_path=raw_vid_path,
                                    output_path=final_path,
                                    format_type=edit_format,
                                    logo_path=edit_logo_path if edit_use_logo else None,
                                    logo_position=edit_logo_pos,
                                    srt_path=sub_burn_path,
                                    font_name=edit_font_name, font_size=edit_font_size,
                                    primary_color=edit_primary_color, outline_color=edit_outline_color,
                                    border_style=edit_border_style, bold=edit_bold,
                                    alignment=edit_alignment, margin_v=edit_margin_v,
                                    back_color=edit_back_color,
                                    portrait_fill=edit_portrait_fill,
                                    portrait_bg_color=edit_portrait_bg_color,
                                    portrait_bg_color2=edit_portrait_bg_color2,
                                    portrait_bg_image=edit_portrait_bg_image,
                                    portrait_bg_video=edit_portrait_bg_video,
                                    portrait_show_top_bar=edit_show_top,
                                    portrait_show_bottom_bar=edit_show_bottom,
                                    portrait_top_text=edit_top_text,
                                    portrait_bottom_text=edit_bottom_text,
                                    portrait_text_size=edit_portrait_text_size,
                                )

                            st.session_state['clip_configs'][clip_idx] = {
                                **render_cfg,
                                'start_time': edit_start_time, 'end_time': edit_end_time,
                                'logo_pos': edit_logo_pos, 'use_logo': edit_use_logo,
                                'logo_path': edit_logo_path, 'enable_subtitle': edit_enable_sub,
                                'preset': edit_preset,
                                'portrait_fill': edit_portrait_fill,
                                'portrait_bg_color': edit_portrait_bg_color,
                                'portrait_bg_color2': edit_portrait_bg_color2,
                                'portrait_bg_image': edit_portrait_bg_image,
                                'portrait_bg_video': edit_portrait_bg_video,
                                'portrait_show_top': edit_show_top,
                                'portrait_show_bottom': edit_show_bottom,
                                'portrait_top_text': edit_top_text,
                                'portrait_bottom_text': edit_bottom_text,
                                'portrait_text_size': edit_portrait_text_size,
                            }
                            st.session_state['exported_files'][clip_idx] = final_path
                            st.success("✅ Klip berhasil diperbarui!")
                            st.rerun()

    # ---- Momen Menarik Lainnya ----
    if clips:
        uncut_clips = [(i, c) for i, c in enumerate(clips) if i not in st.session_state['exported_files']]

        if uncut_clips:
            st.markdown('<div class="section-divider"><div class="section-divider-text">🔍 Momen Lainnya (Belum Dipotong)</div></div>', unsafe_allow_html=True)

            with st.expander("🔍 Tampilkan Semua Momen Menarik", expanded=not bool(st.session_state.get('exported_files'))):
                col_list, col_preview_pane = st.columns([3, 2])

                with col_list:
                    for i, clip in uncut_clips:
                        dur = clip['end_time'] - clip['start_time']
                        source = clip['source']
                        vscore = clip.get('viral_score', 0)

                        st.markdown(f"""
                        <div class="clip-card">
                            <div class="clip-title">
                                {clip['title']}
                                {get_source_badge(source)}
                            </div>
                            <div class="clip-meta">
                                <span class="time-pill">
                                    <span class="tv">{fmt_time(clip['start_time'])}</span>
                                    <span class="ts">→</span>
                                    <span class="tv">{fmt_time(clip['end_time'])}</span>
                                    <span class="ts">({int(dur)} dtk)</span>
                                </span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        s_color = "#f43f5e" if vscore >= 75 else "#a855f7"
                        st.markdown(f"""
                        <div style='background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:8px;padding:8px 12px;margin-bottom:10px;'>
                            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;'>
                                <span style='font-size:0.72rem;font-weight:600;color:#64748b;'>⚡ Potensi Viral</span>
                                <span style='font-size:0.85rem;font-weight:800;color:{s_color};font-family:"Space Grotesk",sans-serif;'>🔥 {vscore}%</span>
                            </div>
                            <div style='background:rgba(255,255,255,0.05);height:4px;border-radius:2px;overflow:hidden;'>
                                <div style='background:linear-gradient(90deg,#a855f7,#ec4899);width:{vscore}%;height:100%;border-radius:2px;'></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        col_p, col_c = st.columns(2)
                        with col_p:
                            if st.button("▶ Preview", key=f"uncut_prev_{i}", use_container_width=True):
                                st.session_state['preview_clip_index'] = i
                                st.rerun()
                        with col_c:
                            btn_cut = st.button("✂️ Potong Ini", key=f"uncut_cut_{i}", use_container_width=True)

                        if btn_cut:
                            with st.spinner(f"⏳ Memotong {clip['title']}…"):
                                try:
                                    raw_path = download_video_clip(url_input, clip['start_time'], clip['end_time'], meta['id'], selected_quality)
                                    if not os.path.exists(raw_path):
                                        raise Exception("File tidak ditemukan setelah download")

                                    st.session_state['raw_video_files'][i] = raw_path

                                    clip_srt = None
                                    srt_out = os.path.join(DOWNLOADS_DIR, f"clip_{meta['id']}_{int(clip['start_time'])}_{int(clip['end_time'])}.srt")

                                    if enable_subtitle:
                                        if sub_source == "📺 YouTube Auto-Captions — Instan" and st.session_state.get('subtitle_path'):
                                            clip_srt = slice_srt(st.session_state['subtitle_path'], clip['start_time'], clip['end_time'], srt_out)
                                        if not clip_srt and check_whisper_available():
                                            clip_srt = generate_whisper_srt(raw_path, srt_out, model_size=whisper_model_size, language=transcribe_lang)

                                    srt_content_uc = ""
                                    if clip_srt and os.path.exists(clip_srt):
                                        try:
                                            with open(clip_srt, "r", encoding="utf-8") as sf:
                                                srt_content_uc = sf.read()
                                        except Exception:
                                            pass
                                    st.session_state['clip_srts'][i] = srt_content_uc
                                    st.session_state['clip_srt_cues'][i] = parse_srt_content(srt_content_uc)

                                    auto_top_uc = meta.get('title', '')[:50] if portrait_show_top else ""
                                    auto_bot_uc = "#fyp #viral #shorts #yxgclip" if portrait_show_bottom else ""

                                    st.session_state['clip_configs'][i] = {
                                        'font_name': sub_font, 'font_size': sub_size,
                                        'primary_color': sub_color_hex, 'outline_color': sub_outline_hex,
                                        'border_style': 1, 'bold': False, 'alignment': 2, 'margin_v': 25,
                                        'back_color': '&H80000000',
                                        'start_time': clip['start_time'], 'end_time': clip['end_time'],
                                        'format_type': layout_format, 'logo_pos': logo_pos,
                                        'use_logo': bool(uploaded_logo), 'logo_path': saved_logo_path,
                                        'enable_subtitle': enable_subtitle, 'preset': sub_preset,
                                        'portrait_fill': portrait_fill, 'portrait_bg_color': portrait_bg_color,
                                        'portrait_bg_color2': portrait_bg_color2, 'portrait_bg_image': portrait_bg_image_path,
                                        'portrait_bg_video': portrait_bg_video_path,
                                        'portrait_show_top': portrait_show_top, 'portrait_show_bottom': portrait_show_bottom,
                                        'portrait_top_text': portrait_top_text_val or auto_top_uc,
                                        'portrait_bottom_text': portrait_bottom_text_val or auto_bot_uc,
                                        'portrait_text_size': portrait_text_sz,
                                    }

                                    final_path = os.path.join(DOWNLOADS_DIR, f"final_{meta['id']}_{int(clip['start_time'])}_{int(clip['end_time'])}.mp4")
                                    if os.path.exists(final_path):
                                        try: os.remove(final_path)
                                        except Exception: pass

                                    sub_burn_path_uc = clip_srt
                                    if clip_srt and os.path.exists(clip_srt):
                                        ass_out_uc = srt_out.replace(".srt", ".ass")
                                        convert_srt_to_ass(clip_srt, ass_out_uc, st.session_state['clip_configs'][i])
                                        sub_burn_path_uc = ass_out_uc

                                    cfg_uc = st.session_state['clip_configs'][i]
                                    process_video_effects(
                                        input_path=raw_path, output_path=final_path,
                                        format_type=layout_format,
                                        logo_path=saved_logo_path if uploaded_logo else None,
                                        logo_position=logo_pos, srt_path=sub_burn_path_uc,
                                        font_name=sub_font, font_size=sub_size,
                                        primary_color=sub_color_hex, outline_color=sub_outline_hex,
                                        portrait_fill=cfg_uc.get('portrait_fill', 'blur'),
                                        portrait_bg_color=cfg_uc.get('portrait_bg_color', '#000000'),
                                        portrait_bg_color2=cfg_uc.get('portrait_bg_color2', '#1a1a2e'),
                                        portrait_bg_image=cfg_uc.get('portrait_bg_image'),
                                        portrait_bg_video=cfg_uc.get('portrait_bg_video'),
                                        portrait_show_top_bar=cfg_uc.get('portrait_show_top', True),
                                        portrait_show_bottom_bar=cfg_uc.get('portrait_show_bottom', True),
                                        portrait_top_text=cfg_uc.get('portrait_top_text', ''),
                                        portrait_bottom_text=cfg_uc.get('portrait_bottom_text', ''),
                                        portrait_text_size=cfg_uc.get('portrait_text_size', 18),
                                    )
                                    if os.path.exists(final_path):
                                        st.session_state['exported_files'][i] = final_path
                                        st.success(f"✅ {clip['title']} berhasil dipotong!")
                                        st.rerun()
                                except Exception as err:
                                    st.error(f"❌ Gagal memotong: {str(err)}")

                with col_preview_pane:
                    st.markdown("""
                    <div class="glass-card" style="border-color:rgba(168,85,247,0.2); position:sticky; top:15px;">
                        <div class="card-header">
                            <div class="card-icon">📺</div>
                            <div>
                                <div class="card-title">Live Preview</div>
                                <div class="card-desc">Preview potongan YouTube</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    preview_idx = st.session_state.get('preview_clip_index', 0)
                    if preview_idx in [x[0] for x in uncut_clips] and preview_idx < len(clips):
                        p_clip = clips[preview_idx]
                        st.markdown(f"<div style='margin:6px 0 8px; font-size:0.85rem; font-weight:600; color:#a855f7;'>▶ {p_clip['title']}</div>", unsafe_allow_html=True)
                        render_youtube_preview(meta['id'], p_clip['start_time'], p_clip['end_time'])
                    else:
                        st.markdown("""
                        <div style="text-align:center; padding:40px 20px; color:#475569;">
                            <div style="font-size:2rem; margin-bottom:8px;">📺</div>
                            <div style="font-size:0.82rem;">Klik Preview di sebelah kiri</div>
                        </div>
                        """, unsafe_allow_html=True)

# ---- Footer ----
st.markdown("""
<div class="app-footer">
    <span>YXGClip v3.0</span> — Auto YouTube Multi-Clipper &middot; Streamlit · yt-dlp · FFmpeg<br>
    <span style="font-size:0.62rem; color:#1e293b; -webkit-text-fill-color:#334155; background:none;">Portrait 9:16 · TikTok · Reels · Shorts</span>
</div>
""", unsafe_allow_html=True)
