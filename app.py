# ==============================================================================
# CLIPPER STUDIO v2.0 — AUTO MULTI-CLIP YOUTUBE CLIPPER
# ==============================================================================
# Fitur Utama:
# 1. Deteksi otomatis momen menarik (Chapters + Most Replayed Heatmap + Fallback)
# 2. Preview clip via YouTube embed (tanpa download penuh)
# 3. Multi-clip selection — pilih & export beberapa clip sekaligus
# 4. Subtitle otomatis dari YouTube auto-captions (burn via FFmpeg)
# 5. Crop portrait 9:16, watermark logo kustom
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

# Whisper untuk generate subtitle lokal (fallback jika YouTube tidak punya caption)
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
# 2. CSS PREMIUM
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    :root {
        --bg-color: #09090b; /* Pure dark slate/black (Zinc 950) */
        --card-bg: #18181b; /* Dark card background (Zinc 900) */
        --border-color: #27272a; /* Clean subtle border (Zinc 800) */
        --border-hover: #3f3f46; /* Zinc 700 */
        --accent-color: #ffffff; /* Pure white matching the logo */
        --accent-text: #09090b; /* Dark text for white background */
        --text-primary: #f4f4f5; /* Zinc 100 */
        --text-muted: #71717a; /* Zinc 500 */
    }

    html, body, [class*="css"] { 
        font-family: 'Inter', sans-serif; 
    }
    
    .stApp { 
        background-color: var(--bg-color);
        color: var(--text-primary);
    }
    
    #MainMenu, footer { visibility: hidden; }

    /* ---- SCROLLBAR ---- */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--border-hover); }

    /* ---- STEP INDICATOR ---- */
    .step-track { 
        display: flex; 
        justify-content: center; 
        align-items: center; 
        gap: 0; 
        margin-bottom: 40px; 
        padding: 0 20px; 
    }
    .step-node { 
        display: flex; 
        flex-direction: column; 
        align-items: center; 
        gap: 10px; 
        min-width: 130px; 
        position: relative; 
        z-index: 2; 
    }
    .step-circle {
        width: 34px; 
        height: 34px; 
        border-radius: 50%; 
        display: flex; 
        align-items: center; 
        justify-content: center;
        font-weight: 600; 
        font-size: 0.9rem; 
        transition: all 0.2s ease;
        border: 2px solid var(--border-color);
        background: var(--bg-color);
        color: var(--text-muted);
    }
    .step-circle.done { 
        background: var(--accent-color); 
        color: var(--accent-text); 
        border-color: var(--accent-color);
    }
    .step-circle.active { 
        background: var(--bg-color); 
        color: var(--accent-color); 
        border-color: var(--accent-color);
    }
    .step-label { 
        font-size: 0.75rem; 
        font-weight: 600; 
        text-transform: uppercase; 
        letter-spacing: 0.5px; 
        text-align: center; 
    }
    .step-label.done { color: var(--accent-color); } 
    .step-label.active { color: var(--accent-color); } 
    .step-label.pending { color: var(--text-muted); }
    
    .step-line { 
        flex: 1; 
        height: 2px; 
        margin: 0 -10px; 
        margin-bottom: 22px; 
        z-index: 1; 
        min-width: 40px; 
        background: var(--border-color);
    }
    .step-line.done { background: var(--accent-color); } 

    /* ---- CARDS ---- */
    .glass-card {
        background: var(--card-bg) !important; 
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important; 
        padding: 24px !important; 
        margin-bottom: 20px !important;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }
    .glass-card:hover { 
        border-color: var(--border-hover) !important;
    }
    
    .card-header { 
        display: flex; 
        align-items: center; 
        gap: 14px; 
        margin-bottom: 16px; 
    }
    
    .card-icon {
        width: 38px; 
        height: 38px; 
        border-radius: 8px; 
        display: flex; 
        align-items: center;
        justify-content: center; 
        font-size: 1.15rem; 
        flex-shrink: 0;
        background: #27272a !important;
        border: 1px solid var(--border-color) !important;
        color: #e4e4e7 !important;
    }
    
    .card-title { 
        font-size: 1.05rem; 
        font-weight: 700; 
        color: var(--text-primary); 
        margin: 0 0 2px 0; 
        letter-spacing: -0.2px;
    }
    .card-desc { 
        font-size: 0.8rem; 
        color: var(--text-muted); 
        margin: 0; 
        font-weight: 400;
    }

    /* ---- META GRID ---- */
    .meta-grid { 
        display: grid; 
        grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); 
        gap: 12px; 
        margin-top: 18px; 
    }
    .meta-item {
        background: #27272a; 
        border: 1px solid var(--border-color);
        border-radius: 8px; 
        padding: 14px 12px; 
        text-align: center; 
        transition: border-color 0.2s ease;
    }
    .meta-item:hover { 
        border-color: var(--border-hover); 
    }
    .meta-value { 
        font-size: 1.25rem; 
        font-weight: 700; 
        color: #fff; 
        margin-bottom: 2px; 
    }
    .meta-key { 
        font-size: 0.65rem; 
        color: var(--text-muted); 
        text-transform: uppercase; 
        letter-spacing: 0.5px; 
        font-weight: 600;
    }
    .meta-title-text { 
        font-size: 1rem; 
        font-weight: 600; 
        color: var(--text-primary); 
        margin-top: 14px; 
        line-height: 1.4; 
        border-left: 3px solid var(--accent-color);
        padding-left: 10px;
    }

    /* ---- CLIP CARD ---- */
    .clip-card {
        background: #18181b; 
        border: 1px solid var(--border-color);
        border-radius: 10px; 
        padding: 16px; 
        margin-bottom: 12px;
        transition: all 0.2s ease;
    }
    .clip-card:hover { 
        border-color: var(--accent-color); 
        background: #27272a; 
    }
    .clip-title { 
        font-size: 0.95rem; 
        font-weight: 600; 
        color: var(--text-primary); 
        margin-bottom: 8px; 
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .clip-meta { 
        font-size: 0.8rem; 
        color: var(--text-muted); 
    }
    .clip-badge {
        display: inline-block; 
        padding: 2px 8px; 
        border-radius: 6px; 
        font-size: 0.65rem;
        font-weight: 700; 
        text-transform: uppercase; 
        letter-spacing: 0.5px; 
        border: 1px solid transparent;
    }
    .badge-chapter { background: #27272a; color: #fff; border-color: var(--border-color); }
    .badge-heatmap { background: #27272a; color: #fff; border-color: var(--border-color); }
    .badge-auto { background: #27272a; color: #fff; border-color: var(--border-color); }

    /* ---- TIME PILLS ---- */
    .time-pill {
        display: inline-flex; 
        align-items: center; 
        gap: 6px;
        background: #09090b; 
        border: 1px solid var(--border-color);
        border-radius: 6px; 
        padding: 4px 10px; 
        font-size: 0.8rem;
    }
    .time-pill .tv { font-weight: 700; color: var(--text-primary); }
    .time-pill .ts { color: var(--text-muted); }

    /* ---- SIDEBAR WRAPPER ---- */
    section[data-testid="stSidebar"] { 
        background: #09090b !important; 
        border-right: 1px solid var(--border-color) !important; 
    }
    .sidebar-section-title { 
        font-size: 0.68rem; 
        font-weight: 700; 
        text-transform: uppercase; 
        letter-spacing: 1px; 
        color: var(--text-muted); 
        margin: 24px 0 10px; 
    }

    /* ---- SaaS WHITE/MONO BUTTONS ---- */
    div.stButton > button {
        background-color: var(--accent-color) !important; 
        color: var(--accent-text) !important; 
        border: 1px solid var(--accent-color) !important;
        padding: 10px 20px !important; 
        border-radius: 8px !important; 
        font-weight: 600 !important; 
        font-size: 0.9rem !important; 
        width: 100%;
        transition: all 0.2s ease !important; 
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
    }
    div.stButton > button:hover { 
        background-color: #e4e4e7 !important; 
        border-color: #e4e4e7 !important;
        transform: none !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
    }
    div.stButton > button:active {
        transform: scale(0.98) !important;
    }
    
    div.stDownloadButton > button {
        background-color: #27272a !important; 
        color: #ffffff !important;
        border: 1px solid var(--border-color) !important; 
        border-radius: 8px !important; 
        font-weight: 600 !important;
        padding: 10px 20px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05) !important;
    }
    div.stDownloadButton > button:hover { 
        background-color: #3f3f46 !important;
        border-color: #3f3f46 !important;
        transform: none !important;
    }

    /* ---- FORM INPUTS ---- */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        background: #18181b !important; 
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important; 
        color: #fff !important; 
        padding: 10px 14px !important; 
        font-size: 0.9rem !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus { 
        border-color: var(--accent-color) !important; 
        box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.2) !important; 
    }
    
    .stSelectbox > div > div { 
        background: #18181b !important; 
        border: 1px solid var(--border-color) !important; 
        border-radius: 8px !important; 
        transition: all 0.2s ease !important;
        padding: 2px 4px !important;
    }
    
    .stSlider > div > div > div > div { 
        background: var(--accent-color) !important; 
    }
    
    div[data-testid="stAlert"] { 
        border-radius: 8px !important; 
        border: 1px solid var(--border-color) !important;
        background: #18181b !important;
        padding: 16px !important;
    }

    /* ---- FOOTER ---- */
    .app-footer { 
        text-align: center; 
        padding: 24px 0 16px; 
        color: var(--text-muted); 
        font-size: 0.75rem; 
        border-top: 1px solid var(--border-color); 
        margin-top: 40px; 
        font-weight: 500;
        letter-spacing: 0.3px;
    }
</style>

""", unsafe_allow_html=True)

# ==============================================================================
# 3. FOLDER & SESSION STATE
# ==============================================================================
DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# Opsi dasar yt-dlp untuk bypass bot-detection YouTube (403 Forbidden).
# default menggunakan web, android, ios, dll. Kita kecualikan android_sdkless karena sering diblokir 403 oleh YouTube.
YDL_EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['default', '-android_sdkless'],
    }
}

def get_ydl_opts(extra: dict = None) -> dict:
    """Buat yt-dlp options dengan cookies (jika ada) untuk bypass 403."""
    cookie_path = os.path.join(DOWNLOADS_DIR, "yt_cookies.txt")
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extractor_args': YDL_EXTRACTOR_ARGS,
        'geo_bypass': True,
        'socket_timeout': 30,
        'retries': 5,
    }
    if os.path.exists(cookie_path):
        opts['cookiefile'] = cookie_path
    if extra:
        opts.update(extra)
    return opts

defaults = {
    'video_metadata': None,
    'current_url': "",
    'clips': [],               # List of detected clips
    'selected_clips': {},      # {index: bool} tracking selected clips
    'subtitle_path': None,     # Path to downloaded SRT
    'subtitle_lang': None,     # Language of downloaded subtitle
    'exported_files': {},      # {clip_index: file_path} of exported clips
    'raw_video_files': {},     # {clip_index: file_path} of raw video clips
    'clip_srts': {},           # {clip_index: srt_content_str}
    'clip_configs': {},        # {clip_index: config_dict}
    'clip_srt_cues': {},       # {clip_index: list of parsed cues}
    'export_running': False,
    'preview_clip_index': 0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================================
# 4. UTILITY FUNCTIONS
# ==============================================================================

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
        # AABBGGRR
        b = clean[2:4]
        g = clean[4:6]
        r = clean[6:8]
        return f"#{r}{g}{b}"
    elif len(clean) == 6:
        # BBGGRR
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
    """Mengambil seluruh metadata video: info dasar, chapters, heatmap, dan subtitle yang tersedia."""
    ydl_opts = get_ydl_opts({'skip_download': True})
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)

            # Chapters
            raw_chapters = info.get('chapters', []) or []
            chapters = []
            for idx, ch in enumerate(raw_chapters):
                chapters.append({
                    'index': idx,
                    'title': ch.get('title', f"Bab {idx+1}"),
                    'start_time': ch.get('start_time', 0.0),
                    'end_time': ch.get('end_time', 0.0)
                })

            # Heatmap (Most Replayed)
            heatmap = info.get('heatmap') or []

            # Subtitle availability
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
    """
    Analisis data heatmap YouTube untuk menemukan segment paling populer.
    Mengembalikan list clip rekomendasi berdasarkan peak engagement.
    """
    if not heatmap_data or not isinstance(heatmap_data, list):
        return []

    # Pastikan data valid
    valid_data = []
    for seg in heatmap_data:
        if isinstance(seg, dict) and 'start_time' in seg and 'end_time' in seg and 'value' in seg:
            valid_data.append(seg)
    if not valid_data:
        return []

    # Hitung threshold: top 25% nilai
    sorted_vals = sorted([s['value'] for s in valid_data], reverse=True)
    threshold_idx = max(1, len(sorted_vals) // 4)
    threshold = sorted_vals[min(threshold_idx, len(sorted_vals)-1)]

    # Cari region kontinu di atas threshold
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

    # Sort by peak value, ambil top N
    peaks.sort(key=lambda x: x['max_value'], reverse=True)
    peaks = peaks[:max_clips]

    # Enforce min/max durasi
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


def analyze_clip_transcript(srt_path, start_time, end_time):
    """
    Menganalisis teks subtitle dalam rentang waktu tertentu.
    Mengembalikan dict berisi:
    - keywords_found: list of keywords
    - hook_score: float (0.0 - 1.0)
    - text_snippet: str
    """
    if not srt_path or not os.path.exists(srt_path):
        return {"keywords_found": [], "hook_score": 0.0, "text_snippet": ""}
    
    try:
        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return {"keywords_found": [], "hook_score": 0.0, "text_snippet": ""}
    
    blocks = content.strip().split('\n\n')
    clip_texts = []
    
    # Kata kunci bernilai viral tinggi
    hooks_indo = ["rahasia", "tips", "trik", "penting", "menarik", "lucu", "ngakak", "keren", "parah", "gokil", "anjir", "gila", "hebat", "kaget", "syok", "sukses", "gagal", "tahu gak", "pernah gak", "bagaimana", "kenapa"]
    hooks_eng = ["secret", "viral", "fail", "success", "shocking", "funny", "laugh", "hack", "tips", "wow", "amazing", "crazy", "did you know", "why", "how to"]
    
    keywords_found = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        # Cari baris timestamp
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
        
        # Cek overlap
        if sub_end <= start_time or sub_start >= end_time:
            continue
            
        text = ' '.join(lines[time_line_idx + 1:])
        clip_texts.append(text)
        
        # Scan kata kunci
        text_lower = text.lower()
        for kw in hooks_indo + hooks_eng:
            if kw in text_lower and kw not in keywords_found:
                keywords_found.append(kw)
                
    full_text = " ".join(clip_texts)
    
    # Hitung hook score
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
    """
    Menghitung skor potensi viral berdasarkan sumber deteksi dan analisis teks.
    """
    base_scores = {
        'heatmap': 0.75,
        'chapter': 0.65,
        'auto': 0.40
    }
    score = base_scores.get(clip['source'], 0.50)
    reasons = []
    
    if clip['source'] == 'heatmap':
        score += min(0.15, clip.get('score', 0.0) * 0.1)
        reasons.append("🔥 Momen paling sering diputar penonton (Most Replayed)")
    elif clip['source'] == 'chapter':
        reasons.append("📖 Bagian dari bab/chapter video yang terstruktur")
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


def detect_highlights(metadata, target_dur=60, srt_path=None):
    """
    Menggabungkan semua sumber deteksi momen menarik:
    1. YouTube Chapters (jika ada)
    2. Most Replayed / Heatmap peaks (jika ada)
    3. Fallback: bagi rata per target_dur detik (jika tidak ada sumber lain)
    Mengisi data viral_score dan viral_reasons pada tiap klip.
    """
    clips = []
    duration = metadata['duration']

    # 1. Chapters
    for ch in metadata.get('chapters', []):
        dur = ch['end_time'] - ch['start_time']
        if dur > 3:  # Skip chapter < 3 detik
            clips.append({
                'title': f"📖 {ch['title']}",
                'start_time': ch['start_time'],
                'end_time': ch['end_time'],
                'source': 'chapter',
                'score': 0.8
            })

    # 2. Heatmap peaks
    heatmap_clips = parse_heatmap_peaks(metadata.get('heatmap', []), duration, max_clip_dur=target_dur)
    
    # Deduplikasi: jangan tambah heatmap clip yang terlalu overlap dengan chapter
    for hc in heatmap_clips:
        is_duplicate = False
        for existing in clips:
            overlap_start = max(hc['start_time'], existing['start_time'])
            overlap_end = min(hc['end_time'], existing['end_time'])
            if overlap_end > overlap_start:
                overlap_dur = overlap_end - overlap_start
                hc_dur = hc['end_time'] - hc['start_time']
                if overlap_dur / hc_dur > 0.5:  # >50% overlap → skip
                    is_duplicate = True
                    break
        if not is_duplicate:
            clips.append(hc)

    # 3. Fallback: bagi rata jika tidak ada clip terdeteksi
    if not clips:
        clip_dur = target_dur
        pos = 0.0
        idx = 1
        while pos < duration:
            end = min(pos + clip_dur, duration)
            if end - pos >= 5:  # Minimal 5 detik
                clips.append({
                    'title': f"✂️ Segment #{idx}",
                    'start_time': round(pos, 1),
                    'end_time': round(end, 1),
                    'source': 'auto',
                    'score': 0.5
                })
                idx += 1
            pos = end

    # Tambahkan skor viral dan penjelasan
    for clip in clips:
        score, reasons = calculate_viral_score(clip, srt_path)
        clip['viral_score'] = score
        clip['viral_reasons'] = reasons

    # Sort berdasarkan waktu
    clips.sort(key=lambda x: x['start_time'])

    # Limit ke 8 clip maksimal
    return clips[:8]


def convert_srt_to_ass(srt_path, ass_path, cfg):
    """
    Mengonversi berkas SRT ke ASS dengan gaya desain modern/viral.
    Mendukung auto-split kata, huruf kapital, dan karaoke highlight.
    """
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

    # Baca konfigurasi
    font_name = cfg.get('font_name', 'Arial')
    font_size = cfg.get('font_size', 20)
    primary_color = cfg.get('primary_color', '&H00FFFFFF')  # format ASS &H00BBGGRR
    outline_color = cfg.get('outline_color', '&H00000000')
    back_color = cfg.get('back_color', '&H80000000')
    border_style = cfg.get('border_style', 1)
    bold = cfg.get('bold', False)
    alignment = cfg.get('alignment', 2)
    margin_v = cfg.get('margin_v', 25)
    preset = cfg.get('preset', 'Klasik (Kustom)')
    
    # Sesuaikan gaya berdasarkan preset
    bold_val = "-1" if bold else "0"
    
    # Override/atur setting jika menggunakan preset viral
    secondary_color = "&H0000FFFF"  # Default base color before highlight (Yellow)
    if preset == "🔥 Viral TikTok":
        font_name = "Impact"
        font_size = int(font_size * 1.3)
        primary_color = "&H0000FFFF"  # Kuning
        outline_color = "&H00000000"  # Hitam
        border_style = 1
        bold_val = "-1"
        alignment = 2  # Tengah bawah
    elif preset == "🔥 Karaoke Highlight":
        font_name = "Arial Black"
        font_size = int(font_size * 1.2)
        primary_color = "&H00FFFFFF"  # Putih
        outline_color = "&H00000000"  # Hitam
        border_style = 1
        bold_val = "-1"
        alignment = 2
    elif preset == "🔥 Karaoke Swipe (Gradual)":
        font_name = "Impact"
        font_size = int(font_size * 1.3)
        primary_color = "&H0000FFFF"  # Kuning (Highlight color)
        secondary_color = "&H00FFFFFF"  # Putih (Base text color)
        outline_color = "&H00000000"  # Hitam
        border_style = 1
        bold_val = "-1"
        alignment = 2
    elif preset == "🔥 Minimalis Modern":
        font_name = "Trebuchet MS"
        font_size = int(font_size * 1.1)
        primary_color = "&H00FFFFFF"  # Putih
        outline_color = "&H00000000"
        border_style = 3  # Backing box
        back_color = "&H99000000"  # Hitam semi transparan
        bold_val = "-1"
        alignment = 2

    # ASS Header
    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 640",
        "PlayResY: 640" if cfg.get('format_type') == "Portrait (9:16)" else "PlayResY: 360",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    
    outline_size = 3 if border_style == 1 else 0
    shadow_size = 1 if border_style == 1 else 0
    
    if preset == "🔥 Viral TikTok" or preset == "🔥 Karaoke Highlight" or preset == "🔥 Karaoke Swipe (Gradual)":
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
        # Parse waktu
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
                karaoke_parts = []
                for w_idx, w in enumerate(words):
                    karaoke_parts.append(f"{{\\k{cs_per_word}}}{w}")
                text = " ".join(karaoke_parts)
                
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
                karaoke_parts = []
                for w_idx, w in enumerate(words):
                    karaoke_parts.append(f"{{\\kf{cs_per_word}}}{w}")
                text = " ".join(karaoke_parts)
                
        elif preset == "🔥 Minimalis Modern":
            text = text.upper()

        ass_lines.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}")

    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(ass_lines) + "\n")

    return ass_path


def download_subtitles(url, video_id, lang='id'):
    """Download subtitle otomatis dari YouTube dalam format SRT."""
    base_name = os.path.join(DOWNLOADS_DIR, f"{video_id}_subs")

    # Bersihkan file SRT lama
    for old_file in glob.glob(f"{base_name}*.srt"):
        try: os.remove(old_file)
        except Exception: pass

    ydl_opts = get_ydl_opts({
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
    })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Cari file SRT yang dihasilkan
    expected = f"{base_name}.{lang}.srt"
    if os.path.exists(expected):
        return expected

    srt_files = glob.glob(f"{base_name}*.srt")
    return srt_files[0] if srt_files else None


def extract_audio_from_clip(video_path, audio_output_path):
    """Ekstrak audio dari file video clip menggunakan FFmpeg (format OGG Vorbis, lebih cepat dari WAV)."""
    # Gunakan OGG vorbis — file lebih kecil, proses I/O lebih cepat
    if audio_output_path.endswith('.wav'):
        audio_output_path = audio_output_path.replace('.wav', '.ogg')
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "libvorbis", "-ar", "16000", "-ac", "1", "-q:a", "2",
        audio_output_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        # Fallback ke WAV jika OGG gagal
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
    """
    Groups individual words from Whisper transcription into short, snappy SRT entries.
    Uses punctuation, word gaps (pauses), and character limits to break segments
    naturally instead of splitting phrases in half.
    """
    srt_entries = []
    idx = 1
    all_words = []

    for seg in segments:
        if is_faster:
            words_list = getattr(seg, 'words', None)
            if words_list:
                for w in words_list:
                    all_words.append({
                        'word': w.word,
                        'start': w.start,
                        'end': w.end
                    })
        else:
            words_list = seg.get("words")
            if words_list:
                for w in words_list:
                    all_words.append({
                        'word': w.get("word", ""),
                        'start': w.get("start", 0.0),
                        'end': w.get("end", 0.0)
                    })

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
            
            # 1. Split if previous word ended with sentence-ending punctuation (., ?, !)
            if any(prev_text.endswith(p) for p in ['.', '?', '!']):
                should_split = True
            # 2. Split if previous word ended with a comma and we have at least 2 words
            elif prev_text.endswith(',') and len(current_words) >= 2:
                should_split = True
            # 3. Split if there is a silent pause between words (> 0.35s)
            elif (w_start - prev_end) > max_gap:
                should_split = True
            # 4. Split if current group has reached the word limit (5 words)
            elif len(current_words) >= max_words:
                should_split = True
            # 5. Split if adding this word would make the character length too long
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
    """
    Generate subtitle SRT dari audio video clip menggunakan Whisper.
    """
    model = load_whisper_model(model_size)
    if model is None:
        return None

    # Ekstrak audio (OGG preferred, fallback WAV)
    audio_path = srt_output_path.replace('.srt', '.ogg')
    extracted = extract_audio_from_clip(video_path, audio_path)
    if not extracted:
        return None
    audio_path = extracted  # extract_audio_from_clip mengembalikan path aktual

    lang_code = language if language != "Auto-Detect" else None

    try:
        srt_entries = []
        # Transcribe dengan Whisper sesuai library yang tersedia
        if WHISPER_TYPE == 'faster':
            segments, info = model.transcribe(audio_path, beam_size=1, language=lang_code, word_timestamps=True, vad_filter=True)
            segments = list(segments)
            srt_entries = group_whisper_words_into_srt(segments, is_faster=True)
        elif WHISPER_TYPE == 'openai':
            transcribe_opts = {
                "word_timestamps": True,
                "temperature": 0.0
            }
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
        # Hapus file audio temporer
        if os.path.exists(audio_path):
            try: os.remove(audio_path)
            except Exception: pass


def slice_srt(srt_path, start_sec, end_sec, output_path):
    """Potong file SRT sesuai rentang waktu dan reset timestamp ke 0."""
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

        # Cari baris timestamp (mengandung ' --> ')
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

        # Cek overlap
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
    """
    Download clip dari YouTube dan potong sesuai rentang waktu.
    Strategi: download full video dulu, lalu potong lokal dengan ffmpeg.
    Ini lebih stabil di cloud environment (Streamlit Cloud) dibanding
    partial download yang membutuhkan ffmpeg sebagai external downloader.
    """
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

    # Download full video jika belum ada
    lock_path = full_video_path + ".lock"
    
    # Jika lock file sangat lama (lebih dari 10 menit), hapus (asumsi sisa crash sebelumnya)
    if os.path.exists(lock_path):
        import time
        try:
            mtime = os.path.getmtime(lock_path)
            if time.time() - mtime > 600:
                os.remove(lock_path)
        except Exception:
            pass

    # Tunggu jika thread/proses lain sedang mendownload video ini
    if os.path.exists(lock_path):
        import time
        start_wait = time.time()
        with st.spinner("⏳ Menunggu unduhan video selesai di proses lain..."):
            while os.path.exists(lock_path):
                time.sleep(1)
                # Maksimal tunggu 5 menit
                if time.time() - start_wait > 300:
                    break

    if not os.path.exists(full_video_path):
        # Buat lock file untuk mencegah race condition
        try:
            with open(lock_path, "w") as f:
                f.write("locked")
                
            ydl_opts = get_ydl_opts({
                'format': fmt_map.get(quality, fmt_map["480p"]),
                'outtmpl': full_video_path,
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
            })
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        finally:
            # Hapus lock file setelah selesai/gagal
            if os.path.exists(lock_path):
                try: os.remove(lock_path)
                except Exception: pass

    if not os.path.exists(full_video_path):
        raise Exception("Gagal mendownload video.")

    # Potong video dengan ffmpeg secara lokal
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
                          back_color="&H80000000"):
    """
    Proses video dengan FFmpeg:
    - Crop portrait 9:16
    - Overlay logo
    - Burn subtitle SRT
    """
    # Jika landscape tanpa efek apapun, salin langsung
    if format_type == "Landscape (16:9)" and not logo_path and not srt_path:
        shutil.copy(input_path, output_path)
        return True

    cmd = ["ffmpeg", "-y", "-i", input_path]
    if logo_path:
        cmd.extend(["-i", logo_path])

    filter_parts = []
    current_layer = "[0:v]"

    # 1. Crop portrait
    if format_type == "Portrait (9:16)":
        filter_parts.append(f"{current_layer}crop=ih*9/16:ih[cropped]")
        current_layer = "[cropped]"

    # 2. Logo overlay
    if logo_path:
        filter_parts.append("[1:v]scale=80:-1[logo_scaled]")
        pos_map = {
            "Kiri Atas": "15:15",
            "Kiri Bawah": "15:main_h-overlay_h-15",
            "Kanan Bawah": "main_w-overlay_w-15:main_h-overlay_h-15",
            "Kanan Atas": "main_w-overlay_w-15:15"
        }
        pos = pos_map.get(logo_position, pos_map["Kanan Atas"])
        filter_parts.append(f"{current_layer}[logo_scaled]overlay={pos}[logoed]")
        current_layer = "[logoed]"

    # 3. Burn subtitles dari SRT / ASS
    if srt_path and os.path.exists(srt_path):
        # Gunakan absolute path dan escape untuk kompatibilitas Linux & Windows
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
        # Append ke rantai filter
        if filter_parts:
            filter_parts.append(f"{current_layer}{sub_filter}[subtitled]")
            current_layer = "[subtitled]"
        else:
            filter_parts.append(f"{current_layer}{sub_filter}[subtitled]")
            current_layer = "[subtitled]"

    if filter_parts:
        filter_str = "; ".join(filter_parts)
        cmd.extend(["-filter_complex", filter_str])
        cmd.extend(["-map", current_layer, "-map", "0:a?", "-c:a", "aac",
                     "-preset", "ultrafast", "-tune", "fastdecode",
                     "-crf", "28", "-threads", "0", output_path])
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
    """Render YouTube embed iframe untuk preview tanpa download."""
    url = f"https://www.youtube.com/embed/{video_id}?start={int(start)}&end={int(end)}&autoplay=0&rel=0"
    components.iframe(url, height=300)


# ==============================================================================
# 7. SIDEBAR
# ==============================================================================

# Path logo yang benar — relatif terhadap file app.py, bukan working directory
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGO_PATH = os.path.join(_APP_DIR, "logo.png")

with st.sidebar:
    if os.path.exists(_LOGO_PATH):
        st.image(_LOGO_PATH, width=95)
    else:
        st.markdown("""
            <div class="sidebar-brand">
                <div class="sidebar-brand-text">YXGClip</div>
                <div class="sidebar-brand-ver">v2.0</div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section-title">🎬 FORMAT OUTPUT</div>', unsafe_allow_html=True)
    layout_format = st.selectbox("Rasio Video", ["Landscape (16:9)", "Portrait (9:16)"],
                                  help="Portrait untuk TikTok, Reels, Shorts.")

    st.markdown('<div class="sidebar-section-title">⏱️ DURASI KLIP</div>', unsafe_allow_html=True)
    target_clip_dur = st.slider(
        "Target Durasi (detik)",
        min_value=15,
        max_value=180,
        value=60,
        step=5,
        help="Durasi target pemotongan klip otomatis (auto-split) dan batas maksimal durasi momen populer."
    )

    st.markdown('<div class="sidebar-section-title">🔥 JUMLAH KLIP VIRAL</div>', unsafe_allow_html=True)
    max_viral_clips = st.slider(
        "Jumlah Momen Dipotong",
        min_value=1,
        max_value=8,
        value=3,
        step=1,
        help="Jumlah klip dengan skor potensi viral tertinggi yang akan langsung dianalisis, dipotong, dan siap diedit."
    )

    st.markdown('<div class="sidebar-section-title">📐 KUALITAS VIDEO</div>', unsafe_allow_html=True)
    kualitas = st.selectbox("Resolusi", ["360p — Cepat", "480p — Standar", "720p — Tinggi", "1080p — Maksimal"], index=1)
    quality_map = {"360p — Cepat":"360p", "480p — Standar":"480p", "720p — Tinggi":"720p", "1080p — Maksimal":"1080p"}
    selected_quality = quality_map[kualitas]

    st.markdown('<div class="sidebar-section-title">🖼️ WATERMARK / LOGO</div>', unsafe_allow_html=True)
    uploaded_logo = st.file_uploader("Unggah Logo", type=["png","jpg","jpeg"], help="Opsional: Logo ditempel di atas video.")
    logo_pos = "Kanan Atas"
    saved_logo_path = None
    if uploaded_logo:
        logo_pos = st.selectbox("Posisi Logo", ["Kanan Atas","Kiri Atas","Kanan Bawah","Kiri Bawah"])
        saved_logo_path = os.path.join(DOWNLOADS_DIR, f"logo_{uploaded_logo.name}")
        try:
            with open(saved_logo_path, "wb") as f:
                f.write(uploaded_logo.getbuffer())
        except Exception:
            pass

    st.markdown('<div class="sidebar-section-title">💬 SUBTITLE OTOMATIS</div>', unsafe_allow_html=True)
    enable_subtitle = st.toggle("Aktifkan Auto-Subtitle", value=True, help="Ambil subtitle otomatis dari YouTube dan burn ke video.")
    
    # Nilai default untuk gaya subtitle
    sub_font = "Arial"
    sub_size = 20
    sub_color_hex = "&H00FFFFFF"
    sub_outline_hex = "&H00000000"
    sub_preset = "Klasik (Kustom)"
    sub_source = "🎙️ Whisper AI (Lokal) — Akurat & Rapi"
    whisper_model_size = "small"
    transcribe_lang = "id"
    
    if enable_subtitle:
        sub_source = st.selectbox(
            "Sumber Subtitel",
            ["🎙️ Whisper AI (Lokal) — Akurat & Rapi", "📺 YouTube Auto-Captions — Instan"],
            index=0,
            help="Whisper AI mentranskripsi audio klip secara lokal dengan tanda baca lengkap. YouTube Auto-Captions langsung menggunakan teks bawaan YouTube."
        )

        if sub_source == "🎙️ Whisper AI (Lokal) — Akurat & Rapi":
            if check_whisper_available():
                col_w1, col_w2 = st.columns(2)
                with col_w1:
                    whisper_model_size = st.selectbox(
                        "Model Whisper",
                        ["base", "small", "medium"],
                        index=1,
                        help="Model 'small' atau 'medium' jauh lebih akurat untuk bahasa Indonesia, tapi sedikit lebih lambat (terutama 'medium' di CPU)."
                    )
                with col_w2:
                    transcribe_lang = st.selectbox(
                        "Bahasa Video",
                        ["id", "Auto-Detect", "en"],
                        index=0,
                        help="Menentukan bahasa manual (misal: 'id' untuk Indonesia) meningkatkan akurasi Whisper secara drastis."
                    )
            else:
                st.warning("⚠️ Whisper AI tidak terdeteksi. Menggunakan YouTube Auto-Captions.")
                sub_source = "📺 YouTube Auto-Captions — Instan"
            
        with st.expander("🎨 Kustomisasi Gaya Subtitle"):
            sub_preset = st.selectbox(
                "Preset Gaya Subtitel",
                ["Klasik (Kustom)", "🔥 Viral TikTok", "🔥 Karaoke Highlight", "🔥 Karaoke Swipe (Gradual)", "🔥 Minimalis Modern"],
                index=0,
                help="Pilih preset gaya subtitle yang sedang viral untuk TikTok, Reels, atau Shorts."
            )
            
            if sub_preset == "Klasik (Kustom)":
                sub_font = st.selectbox(
                    "Jenis Font", 
                    ["Arial", "Arial Black", "Impact", "Comic Sans MS", "Trebuchet MS", "Verdana", "Courier New", "Georgia"],
                    index=0,
                    help="Gunakan font standard sistem Windows."
                )
                sub_size = st.slider("Ukuran Font", min_value=12, max_value=36, value=20, step=2)
                
                sub_color = st.selectbox(
                    "Warna Teks",
                    ["Putih", "Kuning", "Sian (Biru Muda)", "Hijau", "Merah"],
                    index=0
                )
                color_map = {
                    "Putih": "FFFFFF",
                    "Kuning": "00FFFF",
                    "Sian (Biru Muda)": "FFFF00",
                    "Hijau": "00FF00",
                    "Merah": "0000FF"
                }
                sub_color_hex = f"&H00{color_map[sub_color]}"
                
                sub_outline = st.selectbox(
                    "Warna Outline",
                    ["Hitam", "Abu-Abu", "Merah", "Biru"],
                    index=0
                )
                outline_map = {
                    "Hitam": "000000",
                    "Abu-Abu": "808080",
                    "Merah": "0000FF",
                    "Biru": "FF0000"
                }
                sub_outline_hex = f"&H00{outline_map[sub_outline]}"
            else:
                sub_font = "Arial"
                sub_size = 20
                sub_color_hex = "&H00FFFFFF"
                sub_outline_hex = "&H00000000"

    # === COOKIES YOUTUBE ===
    st.markdown('<div class="sidebar-section-title">🍪 COOKIES YOUTUBE</div>', unsafe_allow_html=True)
    st.caption("Unggah cookies.txt jika Anda menemui error 403 (Forbidden).")
    uploaded_cookie = st.file_uploader(
        "Unggah cookies.txt",
        type=["txt"],
        help="Ekspor cookies YouTube dari browser Anda menggunakan ekstensi (seperti 'Get cookies.txt LOCALLY') lalu unggah di sini."
    )

    if uploaded_cookie:
        cookie_path = os.path.join(DOWNLOADS_DIR, "yt_cookies.txt")
        try:
            with open(cookie_path, "wb") as f:
                f.write(uploaded_cookie.getbuffer())
            st.success("✅ Cookies aktif!")
        except Exception:
            st.error("Gagal menyimpan cookies.")
    elif os.path.exists(os.path.join(DOWNLOADS_DIR, "yt_cookies.txt")):
        st.success("✅ Cookies aktif (tersimpan)!")

    st.markdown("---")
    st.markdown('<div style="text-align:center;padding:6px 0;"><div style="font-size:0.68rem;color:#4b5563;">Streamlit · yt-dlp · FFmpeg</div></div>', unsafe_allow_html=True)


# ==============================================================================
# 8. MAIN CONTENT
# ==============================================================================

# ---- HERO ----
col_logo_l, col_logo_c, col_logo_r = st.columns([3, 2, 3])
with col_logo_c:
    if os.path.exists(_LOGO_PATH):
        st.image(_LOGO_PATH, use_container_width=True)
    else:
        st.markdown('<h1 style="text-align: center;">YXGClip</h1>', unsafe_allow_html=True)

st.markdown('<div style="text-align: center; color: var(--text-muted); margin-bottom: 30px; font-weight: 500;">Tempel link YouTube → deteksi momen menarik → preview → download clip.</div>', unsafe_allow_html=True)

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

st.markdown("""
<div class="glass-card">
    <div class="card-header">
        <div class="card-icon indigo">🔗</div>
        <div><div class="card-title">Tempel Link YouTube</div><div class="card-desc">Kami akan otomatis mendeteksi momen menarik dari video</div></div>
    </div>
</div>
""", unsafe_allow_html=True)

col_url, col_go = st.columns([4, 1])
with col_url:
    url_input = st.text_input("URL", placeholder="https://www.youtube.com/watch?v=...", label_visibility="collapsed")
with col_go:
    btn_go = st.button("🎬 Potong & Analisis Momen Viral", use_container_width=True)

# ---- Handle analisis ----
if btn_go and url_input.strip():
    if url_input != st.session_state['current_url']:
        # Reset semua state
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
        st.session_state['current_url'] = url_input

    with st.spinner("🔍 Menganalisis video & mendeteksi momen menarik…"):
        result = get_metadata(url_input)

    if result['status'] == 'error':
        st.error("❌ Gagal menganalisis video.")
        with st.expander("Detail Error"):
            st.code(result['message'])
    else:
        st.session_state['video_metadata'] = result

        # 1. Unduh subtitle otomatis terlebih dahulu (jika diaktifkan) agar bisa dianalisis transkripnya
        srt_path = None
        if enable_subtitle and result.get('sub_langs'):
            lang = result['sub_langs'][0]  # Prioritas pertama
            with st.spinner(f"📝 Mengunduh subtitle otomatis ({lang.upper()})…"):
                try:
                    srt_path = download_subtitles(url_input, result['id'], lang)
                    st.session_state['subtitle_path'] = srt_path
                    st.session_state['subtitle_lang'] = lang
                except Exception:
                    st.session_state['subtitle_path'] = None

        # 2. Deteksi highlights dengan menyertakan srt_path agar dapat menganalisis transkrip secara mendalam
        clips = detect_highlights(result, target_clip_dur, srt_path)
        st.session_state['clips'] = clips
        st.session_state['selected_clips'] = {i: True for i in range(len(clips))}

        # 3. Urutkan klip berdasarkan skor potensi viral tertinggi untuk menentukan klip yang akan dipotong otomatis
        sorted_clips_with_idx = sorted(list(enumerate(clips)), key=lambda x: x[1]['viral_score'], reverse=True)
        top_indices = [idx for idx, clip in sorted_clips_with_idx[:max_viral_clips]]

        # 4. Potong klip terpilih secara langsung (Direct Clipping)
        n_selected = len(top_indices)
        if n_selected > 0:
            exported = {}
            progress = st.progress(0)
            status = st.empty()

            for step_i, clip_idx in enumerate(top_indices):
                clip = clips[clip_idx]
                clip_label = clip['title']
                status.markdown(f"**⏳ Potong Clip {step_i+1}/{n_selected}:** {clip_label} — mengunduh video…")

                try:
                    # Download video range
                    raw_path = download_video_clip(
                        url_input, clip['start_time'], clip['end_time'],
                        result['id'], selected_quality
                    )

                    if not os.path.exists(raw_path):
                        continue

                    st.session_state['raw_video_files'][clip_idx] = raw_path

                    # Potong subtitle
                    clip_srt = None
                    srt_out = os.path.join(DOWNLOADS_DIR, f"clip_{result['id']}_{int(clip['start_time'])}_{int(clip['end_time'])}.srt")
                    
                    if enable_subtitle:
                        if sub_source == "📺 YouTube Auto-Captions — Instan" and st.session_state.get('subtitle_path'):
                            clip_srt = slice_srt(
                                st.session_state['subtitle_path'],
                                clip['start_time'], clip['end_time'], srt_out
                            )
                        if not clip_srt and check_whisper_available():
                            status.markdown(f"**🎙️ Potong Clip {step_i+1}/{n_selected}:** {clip_label} — transkripsi audio otomatis (Whisper)…")
                            clip_srt = generate_whisper_srt(raw_path, srt_out, model_size=whisper_model_size, language=transcribe_lang)

                    # Simpan subtitle di state
                    srt_content = ""
                    if clip_srt and os.path.exists(clip_srt):
                        try:
                            with open(clip_srt, "r", encoding="utf-8") as sf:
                                srt_content = sf.read()
                        except Exception:
                            pass
                    st.session_state['clip_srts'][clip_idx] = srt_content
                    st.session_state['clip_srt_cues'][clip_idx] = parse_srt_content(srt_content)

                    # Simpan konfigurasi klip default
                    st.session_state['clip_configs'][clip_idx] = {
                        'font_name': sub_font,
                        'font_size': sub_size,
                        'primary_color': sub_color_hex,
                        'outline_color': sub_outline_hex,
                        'border_style': 1,
                        'bold': False,
                        'alignment': 2,
                        'margin_v': 25,
                        'back_color': "&H80000000",
                        'start_time': clip['start_time'],
                        'end_time': clip['end_time'],
                        'format_type': layout_format,
                        'logo_pos': logo_pos,
                        'use_logo': bool(uploaded_logo),
                        'logo_path': saved_logo_path,
                        'enable_subtitle': enable_subtitle,
                        'preset': sub_preset
                    }

                    # Render efek & subtitle
                    status.markdown(f"**🎨 Potong Clip {step_i+1}/{n_selected}:** {clip_label} — memproses efek & subtitle…")
                    final_path = os.path.join(DOWNLOADS_DIR, f"final_{result['id']}_{int(clip['start_time'])}_{int(clip['end_time'])}.mp4")

                    if os.path.exists(final_path):
                        try: os.remove(final_path)
                        except Exception: pass

                    # Konversi ke ASS jika diaktifkan untuk style premium
                    sub_burn_path = clip_srt
                    if clip_srt and os.path.exists(clip_srt):
                        ass_out = srt_out.replace(".srt", ".ass")
                        convert_srt_to_ass(clip_srt, ass_out, st.session_state['clip_configs'][clip_idx])
                        sub_burn_path = ass_out

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
                        outline_color=sub_outline_hex
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
    clips = detect_highlights(meta, target_clip_dur, st.session_state.get('subtitle_path'))
    st.session_state['clips'] = clips
    for i in range(len(clips)):
        if i not in st.session_state['selected_clips']:
            st.session_state['selected_clips'][i] = True

    # ---- Info Video ----
    st.markdown(f"""
    <div class="glass-card">
        <div class="card-header">
            <div class="card-icon violet">📺</div>
            <div><div class="card-title">Video Terdeteksi</div><div class="card-desc">{meta['channel']}</div></div>
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
                <div class="meta-value">{'✅ ' + (st.session_state.get('subtitle_lang') or '').upper() if st.session_state.get('subtitle_path') else '—'}</div>
                <div class="meta-key">Subtitle</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ==========================================================
    # STEP 3 — HASIL EKSPOR (DITAMPILKAN DI ATAS JIKA ADA HASIL)
    # ==========================================================
    if st.session_state.get('exported_files'):
        st.markdown("---")
        st.markdown("""
        <div class="glass-card" style="border-color:rgba(16,185,129,0.3); background: rgba(16,185,129,0.02);">
            <div class="card-header">
                <div class="card-icon emerald">✅</div>
                <div>
                    <div class="card-title" style="color:#34d399;">Hasil Potongan Video — Putar & Edit</div>
                    <div class="card-desc">Putar video hasil klip, edit subtitle / font / logo per klip, lalu unduh saat sudah puas</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        for clip_idx, fpath in st.session_state['exported_files'].items():
            if not os.path.exists(fpath):
                continue

            clip = clips[clip_idx] if clip_idx < len(clips) else None
            clip_title = clip['title'] if clip else f"Clip #{clip_idx+1}"

            st.markdown(f"<div style='margin-top: 18px; margin-bottom: 8px; font-weight: 600; color: #f3f4f6;'>🎬 {clip_title}</div>", unsafe_allow_html=True)
            
            # Tampilkan Skor Potensi Viral
            if clip:
                score_color = "#f43f5e" if clip.get('viral_score', 0) >= 75 else "#c084fc"
                score_bar_html = f"""
                <div style='background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 12px; margin-bottom: 12px;'>
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;'>
                        <span style='font-size: 0.8rem; font-weight: 600; color: #d1d5db;'>⚡ Potensi Viral</span>
                        <span style='font-size: 0.95rem; font-weight: 800; color: {score_color};'>🔥 {clip.get('viral_score', 0)}%</span>
                    </div>
                    <div style='background: rgba(255,255,255,0.05); height: 6px; border-radius: 3px; overflow: hidden;'>
                        <div style='background: {score_color}; width: {clip.get('viral_score', 0)}%; height: 100%; border-radius: 3px;'></div>
                    </div>
                """
                if clip.get('viral_reasons'):
                    score_bar_html += "<div style='margin-top: 8px; font-size: 0.72rem; color: #9ca3af; line-height: 1.4;'>"
                    for reason in clip['viral_reasons']:
                        score_bar_html += f"<div>&bull; {reason}</div>"
                    score_bar_html += "</div>"
                score_bar_html += "</div>"
                st.markdown(score_bar_html, unsafe_allow_html=True)
            
            # Preview hasil klip yang ter-render efek & subtitle
            col_vid, col_edt = st.columns([2, 3])
            with col_vid:
                with open(fpath, "rb") as vf:
                    video_data = vf.read()

                st.video(video_data)

                st.download_button(
                    label=f"📥 Unduh — {clip_title}",
                    data=video_data,
                    file_name=f"clipper_{meta['id']}_{clip_idx}.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                    key=f"dl_{clip_idx}"
                )

            with col_edt:
                with st.expander(f"✏️ Edit Klip & Subtitle", expanded=False):
                    # Inisialisasi configs jika belum ada
                    if clip_idx not in st.session_state['clip_configs']:
                        st.session_state['clip_configs'][clip_idx] = {
                            'font_name': sub_font,
                            'font_size': sub_size,
                            'primary_color': sub_color_hex,
                            'outline_color': sub_outline_hex,
                            'border_style': 1,
                            'bold': False,
                            'alignment': 2,
                            'margin_v': 25,
                            'back_color': "&H80000000",
                            'start_time': clip['start_time'] if clip else 0.0,
                            'end_time': clip['end_time'] if clip else 10.0,
                            'format_type': layout_format,
                            'logo_pos': logo_pos,
                            'use_logo': bool(uploaded_logo),
                            'logo_path': saved_logo_path,
                            'enable_subtitle': enable_subtitle
                        }
                    cfg = st.session_state['clip_configs'][clip_idx]
                    srt_str = st.session_state['clip_srts'].get(clip_idx, "")

                    tab_sub, tab_style = st.tabs(["📝 Edit Subtitle", "🎨 Desain & Waktu"])

                    # Tab Subtitle
                    with tab_sub:
                        # Inisialisasi cues dalam session state jika belum ada
                        if clip_idx not in st.session_state['clip_srt_cues']:
                            st.session_state['clip_srt_cues'][clip_idx] = parse_srt_content(srt_str)
                        
                        cues = st.session_state['clip_srt_cues'][clip_idx]
                        edited_cues = []
                        if cues:
                            st.caption("Edit teks & waktu per baris di bawah ini:")
                            for i_cue, cue in enumerate(cues):
                                col_t, col_inp, col_del = st.columns([2, 4, 1])
                                with col_t:
                                    new_time = st.text_input(
                                        f"Waktu {cue['index']}",
                                        value=cue['time_line'],
                                        key=f"srt_time_{clip_idx}_{i_cue}",
                                        label_visibility="collapsed"
                                    )
                                with col_inp:
                                    new_text = st.text_input(
                                        f"Baris {cue['index']}",
                                        value=cue['text'],
                                        key=f"srt_text_{clip_idx}_{i_cue}",
                                        label_visibility="collapsed"
                                    )
                                with col_del:
                                    if st.button("❌", key=f"srt_del_{clip_idx}_{i_cue}"):
                                        st.session_state['clip_srt_cues'][clip_idx].pop(i_cue)
                                        # Re-index
                                        for idx, c in enumerate(st.session_state['clip_srt_cues'][clip_idx]):
                                            c['index'] = str(idx + 1)
                                        st.rerun()
                                # Update cue di state
                                cue['time_line'] = new_time
                                cue['text'] = new_text
                                edited_cues.append(cue)
                        
                        # Tombol Tambah Baris Baru
                        if st.button("➕ Tambah Baris Subtitle", key=f"add_cue_btn_{clip_idx}", use_container_width=True):
                            last_end = "00:00:00,000"
                            if cues:
                                time_line_parts = cues[-1]['time_line'].split(' --> ')
                                if len(time_line_parts) == 2:
                                    last_end = time_line_parts[1]
                            try:
                                start_sec = parse_srt_time(last_end)
                            except Exception:
                                start_sec = 0.0
                            end_sec = start_sec + 3.0
                            new_time_line = f"{fmt_srt_time(start_sec)} --> {fmt_srt_time(end_sec)}"
                            
                            st.session_state['clip_srt_cues'][clip_idx].append({
                                'index': str(len(cues) + 1),
                                'time_line': new_time_line,
                                'text': 'Subtitle baru'
                            })
                            st.rerun()
                        
                        # Selalu sediakan area edit text raw untuk keadaan darurat / tambah manual
                        with st.expander("📝 Edit Raw SRT (Mode Lanjut)"):
                            current_srt_val = build_srt_content(cues) if cues else srt_str
                            raw_srt_edited = st.text_area(
                                "Konten SRT mentah",
                                value=current_srt_val,
                                key=f"srt_raw_{clip_idx}",
                                height=150,
                                help="Format SRT: Indeks, Waktu (Start --> End), dan Teks."
                            )
                            # Jika raw text dirubah oleh user, parse kembali ke cues
                            if raw_srt_edited != current_srt_val:
                                st.session_state['clip_srt_cues'][clip_idx] = parse_srt_content(raw_srt_edited)
                                st.rerun()

                    # Tab Desain & Gaya
                    with tab_style:
                        col_cfg_l, col_cfg_r = st.columns(2)
                        with col_cfg_l:
                            edit_format = st.selectbox(
                                "Rasio Video", ["Landscape (16:9)", "Portrait (9:16)"],
                                index=0 if cfg['format_type'] == "Landscape (16:9)" else 1,
                                key=f"fmt_{clip_idx}"
                            )
                            
                            # File uploader untuk logo kustom klip ini
                            uploaded_clip_logo = st.file_uploader(
                                "Unggah Logo Klip", 
                                type=["png","jpg","jpeg"], 
                                key=f"logo_upload_{clip_idx}",
                                help="Opsional: Logo khusus untuk klip ini (menggantikan logo sidebar)."
                            )
                            
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
                                edit_use_logo = st.checkbox(
                                    "Gunakan Watermark Logo",
                                    value=cfg.get('use_logo', True),
                                    key=f"use_logo_{clip_idx}"
                                )
                                if edit_use_logo:
                                    edit_logo_pos = st.selectbox(
                                        "Posisi Logo", ["Kanan Atas","Kiri Atas","Kanan Bawah","Kiri Bawah"],
                                        index=["Kanan Atas","Kiri Atas","Kanan Bawah","Kiri Bawah"].index(cfg.get('logo_pos', 'Kanan Atas')),
                                        key=f"logo_pos_{clip_idx}"
                                    )
                                    edit_logo_path = logo_to_use
                            else:
                                edit_use_logo = False
                                    
                            edit_enable_sub = st.checkbox(
                                "Aktifkan Subtitle",
                                value=cfg['enable_subtitle'],
                                key=f"en_sub_{clip_idx}"
                            )

                        with col_cfg_r:
                            # Timing adjustment
                            edit_start_time = st.number_input(
                                "Waktu Mulai (detik)",
                                min_value=0.0,
                                max_value=float(meta['duration']),
                                value=float(cfg['start_time']),
                                step=0.5,
                                format="%.1f",
                                key=f"start_t_{clip_idx}"
                            )
                            edit_end_time = st.number_input(
                                "Waktu Selesai (detik)",
                                min_value=0.1,
                                max_value=float(meta['duration']),
                                value=float(cfg['end_time']),
                                step=0.5,
                                format="%.1f",
                                key=f"end_t_{clip_idx}"
                            )

                        if edit_enable_sub:
                            edit_preset = st.selectbox(
                                "Preset Gaya Subtitel",
                                ["Klasik (Kustom)", "🔥 Viral TikTok", "🔥 Karaoke Highlight", "🔥 Karaoke Swipe (Gradual)", "🔥 Minimalis Modern"],
                                index=["Klasik (Kustom)", "🔥 Viral TikTok", "🔥 Karaoke Highlight", "🔥 Karaoke Swipe (Gradual)", "🔥 Minimalis Modern"].index(cfg.get('preset', 'Klasik (Kustom)')),
                                key=f"preset_{clip_idx}"
                            )

                            if edit_preset == "Klasik (Kustom)":
                                st.markdown("<div style='font-size:0.85rem; font-weight:600; color:#a78bfa; margin-top:8px;'>Gaya Font Subtitle</div>", unsafe_allow_html=True)
                                col_f1, col_f2 = st.columns(2)
                                
                                with col_f1:
                                    available_fonts = ["Arial", "Arial Black", "Impact", "Comic Sans MS", "Trebuchet MS", "Verdana", "Courier New", "Georgia"]
                                    font_index = available_fonts.index(cfg['font_name']) if cfg['font_name'] in available_fonts else 0
                                    edit_font_name = st.selectbox(
                                        "Jenis Font", available_fonts,
                                        index=font_index,
                                        key=f"font_name_{clip_idx}"
                                    )
                                    custom_font = st.text_input(
                                        "Font Kustom (Opsional)",
                                        value=cfg['font_name'] if cfg['font_name'] not in available_fonts else "",
                                        key=f"cust_font_{clip_idx}",
                                        placeholder="Masukkan nama font sistem..."
                                    )
                                    if custom_font.strip():
                                        edit_font_name = custom_font.strip()
                                        
                                    edit_font_size = st.slider(
                                        "Ukuran Font",
                                        min_value=12, max_value=48,
                                        value=int(cfg['font_size']),
                                        step=2,
                                        key=f"font_size_{clip_idx}"
                                    )
                                    edit_bold = st.checkbox("Tebalkan Teks (Bold)", value=cfg['bold'], key=f"bold_{clip_idx}")

                                with col_f2:
                                    edit_style_type = st.selectbox(
                                        "Gaya Tampilan", ["Klasik (Outline)", "Modern (Kotak Latar Belakang)"],
                                        index=0 if cfg['border_style'] == 1 else 1,
                                        key=f"border_style_{clip_idx}"
                                    )
                                    edit_border_style = 1 if edit_style_type == "Klasik (Outline)" else 3
                                    
                                    align_opts = {"Bawah (Default)": 2, "Tengah (Center)": 10, "Atas": 6}
                                    edit_align_label = st.selectbox(
                                        "Posisi Subtitle", list(align_opts.keys()),
                                        index=list(align_opts.values()).index(cfg['alignment']),
                                        key=f"align_{clip_idx}"
                                    )
                                    edit_alignment = align_opts[edit_align_label]
                                    
                                    edit_margin_v = st.slider(
                                        "Margin Vertikal (V)",
                                        min_value=5, max_value=200,
                                        value=int(cfg['margin_v']),
                                        step=5,
                                        key=f"margin_v_{clip_idx}"
                                    )

                                # Color selectors
                                col_c1, col_c2 = st.columns(2)
                                with col_c1:
                                    current_hex_text = ass_to_hex_color(cfg['primary_color'])
                                    edit_hex_text = st.color_picker(
                                        "Warna Teks",
                                        value=current_hex_text,
                                        key=f"color_text_{clip_idx}"
                                    )
                                    edit_primary_color = hex_to_ass_color(edit_hex_text)
                                    
                                with col_c2:
                                    color_label = "Warna Outline" if edit_border_style == 1 else "Warna Kotak Latar"
                                    current_hex_out = ass_to_hex_color(cfg['outline_color'] if edit_border_style == 1 else cfg['back_color'])
                                    edit_hex_out = st.color_picker(
                                        color_label,
                                        value=current_hex_out,
                                        key=f"color_out_{clip_idx}"
                                    )
                                    
                                    if edit_border_style == 1:
                                        edit_outline_color = hex_to_ass_color(edit_hex_out)
                                        edit_back_color = "&H80000000"
                                    else:
                                        edit_outline_color = "&H00000000"
                                        raw_ass = hex_to_ass_color(edit_hex_out)
                                        edit_back_color = raw_ass.replace("&H00", "&H80") # 50% opacity
                            else:
                                edit_font_name = "Arial"
                                edit_font_size = 20
                                edit_bold = False
                                edit_border_style = 1
                                edit_alignment = 2
                                edit_margin_v = 25
                                edit_primary_color = "&H00FFFFFF"
                                edit_outline_color = "&H00000000"
                                edit_back_color = "&H80000000"
                        else:
                            edit_font_name = cfg['font_name']
                            edit_font_size = cfg['font_size']
                            edit_bold = cfg['bold']
                            edit_border_style = cfg['border_style']
                            edit_alignment = cfg['alignment']
                            edit_margin_v = cfg['margin_v']
                            edit_primary_color = cfg['primary_color']
                            edit_outline_color = cfg['outline_color']
                            edit_back_color = cfg['back_color']
                            edit_preset = "Klasik (Kustom)"

                    # Tombol Re-render
                    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                    btn_re_render = st.button(
                        "🔄 Terapkan Perubahan & Render Ulang",
                        key=f"re_render_{clip_idx}",
                        use_container_width=True
                    )

                    if btn_re_render:
                        if edit_start_time >= edit_end_time:
                            st.error("❌ Waktu mulai harus lebih kecil dari waktu selesai.")
                        else:
                            # 1. Simpan/Bangun SRT
                            final_srt_str = ""
                            if edit_enable_sub:
                                srt_cues = st.session_state['clip_srt_cues'].get(clip_idx, [])
                                if srt_cues:
                                    final_srt_str = build_srt_content(srt_cues)
                                else:
                                    final_srt_str = raw_srt_edited
                            
                            srt_out = os.path.join(DOWNLOADS_DIR, f"clip_{meta['id']}_{int(edit_start_time)}_{int(edit_end_time)}.srt")
                            if edit_enable_sub and final_srt_str.strip():
                                with open(srt_out, "w", encoding="utf-8") as sf:
                                    sf.write(final_srt_str)
                            
                            # 2. Cek apakah timing berubah -> perlu re-download/slice
                            timing_changed = (edit_start_time != cfg['start_time']) or (edit_end_time != cfg['end_time'])
                            raw_vid_path = st.session_state['raw_video_files'].get(clip_idx)
                            
                            if timing_changed or not raw_vid_path or not os.path.exists(raw_vid_path):
                                with st.spinner("⏳ Mengunduh ulang rentang video baru..."):
                                    raw_vid_path = download_video_clip(
                                        url_input, edit_start_time, edit_end_time,
                                        meta['id'], selected_quality
                                    )
                                    st.session_state['raw_video_files'][clip_idx] = raw_vid_path
                                    
                                # Jika Timing berubah, generate/slice ulang SRT jika belum ada edit manual dari pengguna
                                if edit_enable_sub and (not final_srt_str.strip() or timing_changed):
                                    clip_srt_res = None
                                    if sub_source == "📺 YouTube Auto-Captions — Instan" and st.session_state.get('subtitle_path'):
                                        clip_srt_res = slice_srt(
                                            st.session_state['subtitle_path'],
                                            edit_start_time, edit_end_time,
                                            srt_out
                                        )
                                    if not clip_srt_res and check_whisper_available():
                                        generate_whisper_srt(raw_vid_path, srt_out, model_size=whisper_model_size, language=transcribe_lang)
                                    
                                    # Baca konten srt yang baru
                                    if os.path.exists(srt_out):
                                        with open(srt_out, "r", encoding="utf-8") as sf:
                                            final_srt_str = sf.read()

                            # Tulis ulang subtitle hasil penyesuaian timing ke session state
                            st.session_state['clip_srts'][clip_idx] = final_srt_str
                            st.session_state['clip_srt_cues'][clip_idx] = parse_srt_content(final_srt_str)

                            # 3. Jalankan pemrosesan efek FFmpeg
                            final_path = os.path.join(DOWNLOADS_DIR, f"final_{meta['id']}_{int(edit_start_time)}_{int(edit_end_time)}.mp4")
                            
                            # Pastikan file lama dihapus agar tidak bentrok
                            if os.path.exists(final_path):
                                try: os.remove(final_path)
                                except Exception: pass
                                
                            # Buat temporary config untuk rendering
                            render_cfg = {
                                'font_name': edit_font_name,
                                'font_size': edit_font_size,
                                'primary_color': edit_primary_color,
                                'outline_color': edit_outline_color,
                                'border_style': edit_border_style,
                                'bold': edit_bold,
                                'alignment': edit_alignment,
                                'margin_v': edit_margin_v,
                                'back_color': edit_back_color,
                                'format_type': edit_format,
                                'preset': edit_preset
                             }

                            # Konversi ke ASS jika diaktifkan
                            sub_burn_path = srt_out if edit_enable_sub else None
                            if edit_enable_sub and srt_out and os.path.exists(srt_out):
                                ass_out = srt_out.replace(".srt", ".ass")
                                convert_srt_to_ass(srt_out, ass_out, render_cfg)
                                sub_burn_path = ass_out

                            with st.spinner("🎬 Memproses efek & me-render video..."):
                                process_video_effects(
                                    input_path=raw_vid_path,
                                    output_path=final_path,
                                    format_type=edit_format,
                                    logo_path=edit_logo_path if edit_use_logo else None,
                                    logo_position=edit_logo_pos,
                                    srt_path=sub_burn_path,
                                    font_name=edit_font_name,
                                    font_size=edit_font_size,
                                    primary_color=edit_primary_color,
                                    outline_color=edit_outline_color,
                                    border_style=edit_border_style,
                                    bold=edit_bold,
                                    alignment=edit_alignment,
                                    margin_v=edit_margin_v,
                                    back_color=edit_back_color
                                )
                                
                            # 4. Simpan config & path hasil baru
                            st.session_state['clip_configs'][clip_idx] = {
                                'font_name': edit_font_name,
                                'font_size': edit_font_size,
                                'primary_color': edit_primary_color,
                                'outline_color': edit_outline_color,
                                'border_style': edit_border_style,
                                'bold': edit_bold,
                                'alignment': edit_alignment,
                                'margin_v': edit_margin_v,
                                'back_color': edit_back_color,
                                'start_time': edit_start_time,
                                'end_time': edit_end_time,
                                'format_type': edit_format,
                                'logo_pos': edit_logo_pos,
                                'use_logo': edit_use_logo,
                                'logo_path': edit_logo_path,
                                'enable_subtitle': edit_enable_sub,
                                'preset': edit_preset
                            }
                            st.session_state['exported_files'][clip_idx] = final_path
                            st.success("✅ Klip berhasil diperbarui!")
                            st.rerun()

    # ---- Momen Menarik Lainnya (Belum Dipotong) ----
    if clips:
        uncut_clips = [(i, c) for i, c in enumerate(clips) if i not in st.session_state['exported_files']]
        
        if uncut_clips:
            st.markdown("---")
            with st.expander("🔍 Tampilkan Momen Menarik Lainnya (Belum Dipotong)", expanded=not bool(st.session_state.get('exported_files'))):
                st.markdown("""
                <div class="glass-card" style="margin-top: 10px;">
                    <div class="card-header">
                        <div class="card-icon pink">🔍</div>
                        <div>
                            <div class="card-title">Momen Menarik Lainnya</div>
                            <div class="card-desc">Pilih momen di bawah ini untuk dipotong dan diedit secara instan</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Layout: Kiri daftar klip, Kanan player preview
                col_list, col_preview_pane = st.columns([3, 2])

                with col_list:
                    for i, clip in uncut_clips:
                        dur = clip['end_time'] - clip['start_time']
                        source = clip['source']
                        badge_class = {'chapter': 'badge-chapter', 'heatmap': 'badge-heatmap', 'auto': 'badge-auto'}.get(source, 'badge-auto')
                        badge_label = {'chapter': 'Chapter', 'heatmap': 'Most Replayed', 'auto': 'Auto-Split'}.get(source, source)

                        st.markdown(f"""
                        <div class="clip-card" style="margin-bottom: 8px;">
                            <div class="clip-title">{clip['title']} <span class="clip-badge {badge_class}">{badge_label}</span></div>
                            <div class="clip-meta">
                                <span class="time-pill"><span class="tv">{fmt_time(clip['start_time'])}</span><span class="ts">→</span><span class="tv">{fmt_time(clip['end_time'])}</span><span class="ts">({int(dur)} dtk)</span></span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        # Potensi viral score bar
                        s_color = "#f43f5e" if clip.get('viral_score', 0) >= 75 else "#c084fc"
                        reasons_html = ""
                        if clip.get('viral_reasons'):
                            reasons_html = "<div style='margin-top: 4px; font-size: 0.7rem; color: #9ca3af;'>" + "".join([f"<div>&bull; {r}</div>" for r in clip['viral_reasons']]) + "</div>"

                        st.markdown(f"""
                        <div style='background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; padding: 10px; margin-bottom: 12px;'>
                            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;'>
                                <span style='font-size: 0.72rem; font-weight: 600; color: #d1d5db;'>⚡ Potensi Viral: <span style='color: {s_color}; font-weight:800;'>🔥 {clip.get('viral_score', 0)}%</span></span>
                            </div>
                            <div style='background: rgba(255,255,255,0.05); height: 4px; border-radius: 2px; overflow: hidden; width: 150px;'>
                                <div style='background: {s_color}; width: {clip.get('viral_score', 0)}%; height: 100%; border-radius: 2px;'></div>
                            </div>
                            {reasons_html}
                        </div>
                        """, unsafe_allow_html=True)

                        col_p, col_c = st.columns(2)
                        with col_p:
                            if st.button("🔍 Preview", key=f"uncut_prev_{i}", use_container_width=True):
                                st.session_state['preview_clip_index'] = i
                                st.rerun()
                        with col_c:
                            btn_cut = st.button("✂️ Potong Momen Ini", key=f"uncut_cut_{i}", use_container_width=True)

                        if btn_cut:
                            with st.spinner(f"⏳ Memotong {clip['title']}…"):
                                try:
                                    # 1. Download
                                    raw_path = download_video_clip(
                                        url_input, clip['start_time'], clip['end_time'],
                                        meta['id'], selected_quality
                                    )
                                    if os.path.exists(raw_path):
                                        st.session_state['raw_video_files'][i] = raw_path

                                        # 2. Subtitle
                                        clip_srt = None
                                        srt_out = os.path.join(DOWNLOADS_DIR, f"clip_{meta['id']}_{int(clip['start_time'])}_{int(clip['end_time'])}.srt")
                                        if enable_subtitle:
                                            if sub_source == "📺 YouTube Auto-Captions — Instan" and st.session_state.get('subtitle_path'):
                                                clip_srt = slice_srt(
                                                    st.session_state['subtitle_path'],
                                                    clip['start_time'], clip['end_time'], srt_out
                                                )
                                            if not clip_srt and check_whisper_available():
                                                clip_srt = generate_whisper_srt(raw_path, srt_out, model_size=whisper_model_size, language=transcribe_lang)

                                        srt_content = ""
                                        if clip_srt and os.path.exists(clip_srt):
                                            try:
                                                with open(clip_srt, "r", encoding="utf-8") as sf:
                                                    srt_content = sf.read()
                                            except Exception:
                                                pass
                                        st.session_state['clip_srts'][i] = srt_content
                                        st.session_state['clip_srt_cues'][i] = parse_srt_content(srt_content)

                                        # 3. Config
                                        st.session_state['clip_configs'][i] = {
                                            'font_name': sub_font,
                                            'font_size': sub_size,
                                            'primary_color': sub_color_hex,
                                            'outline_color': sub_outline_hex,
                                            'border_style': 1,
                                            'bold': False,
                                            'alignment': 2,
                                            'margin_v': 25,
                                            'back_color': "&H80000000",
                                            'start_time': clip['start_time'],
                                            'end_time': clip['end_time'],
                                            'format_type': layout_format,
                                            'logo_pos': logo_pos,
                                            'use_logo': bool(uploaded_logo),
                                            'logo_path': saved_logo_path,
                                            'enable_subtitle': enable_subtitle,
                                            'preset': sub_preset
                                        }

                                        # 4. Effects
                                        final_path = os.path.join(DOWNLOADS_DIR, f"final_{meta['id']}_{int(clip['start_time'])}_{int(clip['end_time'])}.mp4")
                                        if os.path.exists(final_path):
                                            try: os.remove(final_path)
                                            except Exception: pass

                                        # Konversi ke ASS jika diaktifkan
                                        sub_burn_path = clip_srt
                                        if clip_srt and os.path.exists(clip_srt):
                                            ass_out = srt_out.replace(".srt", ".ass")
                                            convert_srt_to_ass(clip_srt, ass_out, st.session_state['clip_configs'][i])
                                            sub_burn_path = ass_out

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
                                            outline_color=sub_outline_hex
                                        )
                                        if os.path.exists(final_path):
                                            st.session_state['exported_files'][i] = final_path
                                            st.success(f"✅ {clip['title']} berhasil dipotong!")
                                            st.rerun()
                                except Exception as err:
                                    st.error(f"❌ Gagal memotong: {str(err)}")

                with col_preview_pane:
                    st.markdown("""
                    <div class="glass-card" style="border-color: rgba(168,85,247,0.3); background: rgba(168,85,247,0.02); margin-top: 10px; position: -webkit-sticky; position: sticky; top: 15px;">
                        <div class="card-header" style="padding-bottom: 8px;">
                            <div class="card-icon violet">📺</div>
                            <div>
                                <div class="card-title">Live Preview Player</div>
                                <div class="card-desc">Memutar potongan video YouTube</div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    preview_idx = st.session_state.get('preview_clip_index', 0)
                    if preview_idx in [x[0] for x in uncut_clips] and preview_idx < len(clips):
                        p_clip = clips[preview_idx]
                        st.markdown(f"<div style='margin: 8px 0; font-size: 0.9rem; font-weight: 600; color: #c084fc;'>📺 Sedang Diputar: {p_clip['title']}</div>", unsafe_allow_html=True)
                        render_youtube_preview(meta['id'], p_clip['start_time'], p_clip['end_time'])
                    else:
                        st.info("Pilih klip di sebelah kiri dan klik '🔍 Preview' untuk memutar klip.")

# ---- Footer ----
st.markdown('<div class="app-footer">Clipper Studio v2.0 — Auto YouTube Multi-Clipper &middot; Streamlit + yt-dlp + FFmpeg</div>', unsafe_allow_html=True)
