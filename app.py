"""
Incucyte Timecourse Plotter — Professional Edition
==================================================
Publication-grade, clean light theme.
Uses Plotly for interactive figures + Streamlit wide layout.
"""

import io
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ─────────────────────────────────────────────
#  Page config — must be first Streamlit call
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Incucyte Plotter",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  Global CSS — clean light app theme
# ─────────────────────────────────────────────
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">

    <style>
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }

    [data-testid="stSidebar"] .stTextInput > label,
    [data-testid="stSidebar"] .stSelectbox > label,
    [data-testid="stSidebar"] .stSlider > label,
    [data-testid="stSidebar"] .stNumberInput > label,
    [data-testid="stSidebar"] .stCheckbox > label {
        font-size: 0.75rem !important;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        font-family: 'IBM Plex Mono', monospace !important;
        opacity: 0.65;
    }

    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-top: 3px solid #0ea5e9;
        border-radius: 8px;
        padding: 18px 22px;
        text-align: center;
    }
    .metric-label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.66rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #64748b;
        margin-bottom: 6px;
    }
    .metric-value {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.9rem;
        font-weight: 500;
        color: #0ea5e9;
        line-height: 1;
    }
    .metric-sub {
        font-size: 0.72rem;
        color: #94a3b8;
        margin-top: 4px;
    }

    .section-header {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #64748b;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 6px;
        margin: 28px 0 16px;
    }

    .hero-title {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.9rem;
        font-weight: 500;
        color: #0f172a;
        letter-spacing: -0.02em;
        line-height: 1.1;
    }
    .hero-accent {
        color: #0ea5e9;
    }
    .hero-sub {
        font-size: 0.86rem;
        color: #64748b;
        margin-top: 5px;
        letter-spacing: 0.02em;
    }

    .badge {
        display: inline-block;
        background: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 20px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.68rem;
        color: #0284c7;
        padding: 3px 10px;
        margin-right: 5px;
        letter-spacing: 0.05em;
    }

    [data-testid="stTabs"] button {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.76rem !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border-radius: 0 !important;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #0ea5e9 !important;
        border-bottom: 2px solid #0ea5e9 !important;
    }

    .stDownloadButton > button {
        background: #f0f9ff !important;
        border: 1px solid #bae6fd !important;
        color: #0284c7 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.72rem !important;
        letter-spacing: 0.05em;
        border-radius: 5px !important;
        transition: all 0.18s;
    }
    .stDownloadButton > button:hover {
        background: #0ea5e9 !important;
        border-color: #0ea5e9 !important;
        color: #fff !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
#  Parsing helpers
# ─────────────────────────────────────────────
def _coerce_time(col):
    c = pd.to_numeric(col, errors="coerce")
    if c.notna().all():
        return c.astype(float)
    s = col.astype(str).str.extract(r"([0-9]*\.?[0-9]+)")[0]
    return pd.to_numeric(s, errors="coerce").astype(float)


def _base_group_name(colname: str) -> str:
    m = re.match(r"^(.*)_(R\d+|Rep\d+|rep\d+)$", str(colname))
    return m.group(1) if m else str(colname)


def _read_text_buffer(uploaded_file) -> str:
    raw = uploaded_file.getvalue()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin1")


def _detect_incucyte_export(raw_text: str) -> bool:
    lines = raw_text.splitlines()
    if len(lines) < 2:
        return False
    return lines[0].strip().startswith("Vessel Name:") and "Elapsed" in lines[1]


def _clean_incucyte_group_name(colname: str) -> str:
    s = str(colname)
    s = re.sub(r"\s*\([A-Z]\d+\)\s*$", "", s)
    s = re.sub(r"\s*\(\d+\)\s*\d+\s*K\s*/\s*well\s*", " | ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+\d+\s*mg/ml", "", s, flags=re.IGNORECASE)
    return s.replace(" | ", " - ").strip()


def parse_incucyte_export(uploaded_file) -> pd.DataFrame:
    text = _read_text_buffer(uploaded_file)
    df = pd.read_csv(io.StringIO(text), sep="\t", skiprows=1)
    if "Elapsed" not in df.columns:
        raise ValueError("Incucyte export detected but 'Elapsed' column not found.")

    value_cols = [c for c in df.columns if c not in ["Date Time", "Elapsed"]]
    long = df.melt(
        id_vars=["Elapsed"],
        value_vars=value_cols,
        var_name="raw_col",
        value_name="value",
    ).rename(columns={"Elapsed": "time"})

    long["group"] = long["raw_col"].apply(_clean_incucyte_group_name)

    col_map = pd.DataFrame({"raw_col": value_cols})
    col_map["group"] = col_map["raw_col"].apply(_clean_incucyte_group_name)
    col_map["replicate_num"] = col_map.groupby("group").cumcount() + 1
    col_map["replicate"] = "R" + col_map["replicate_num"].astype(str)

    long = long.merge(
        col_map[["raw_col", "replicate"]],
        on="raw_col",
        how="left",
        validate="many_to_one",
    )

    group_order = pd.unique(col_map["group"]).tolist()
    long["group"] = pd.Categorical(long["group"], categories=group_order, ordered=True)
    long["time"] = _coerce_time(long["time"])
    long["replicate"] = long["replicate"].astype(str)
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["time", "value"])

    return long[["time", "group", "replicate", "value"]].reset_index(drop=True)


def read_incucyte_csv(path_or_buffer) -> pd.DataFrame:
    if hasattr(path_or_buffer, "getvalue"):
        raw_text = _read_text_buffer(path_or_buffer)
        if _detect_incucyte_export(raw_text):
            return parse_incucyte_export(path_or_buffer)

    df = pd.read_csv(path_or_buffer)
    lower_map = {c.lower(): c for c in df.columns}
    cols_lower = set(lower_map.keys())

    if "time" in cols_lower and not {"group", "replicate", "value"}.issubset(cols_lower):
        time_col = lower_map["time"]
        value_cols_in_order = [c for c in df.columns if c != time_col]
        df = df.rename(columns={time_col: "time"})
        long = df.melt(id_vars="time", value_vars=value_cols_in_order, var_name="col", value_name="value")

        m = long["col"].astype(str).str.extract(r"^(.*)_(R\d+|Rep\d+|rep\d+)$")
        has_rep = m.notna().all(axis=1)
        long["group"] = np.where(has_rep, m[0], long["col"].astype(str))
        long["replicate"] = np.where(has_rep, m[1], "R1")

        group_order = []
        seen = set()
        for c in value_cols_in_order:
            base = _base_group_name(c)
            if base not in seen:
                group_order.append(base)
                seen.add(base)

        long["group"] = long["group"].astype(str)
        long["group"] = pd.Categorical(long["group"], categories=group_order, ordered=True)
        long["time"] = _coerce_time(long["time"])
        long["replicate"] = long["replicate"].astype(str)
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long = long.dropna(subset=["time", "value"])
        return long[["time", "group", "replicate", "value"]].reset_index(drop=True)

    required = {"time", "group", "value"}
    if required.issubset(cols_lower):
        df = df.rename(
            columns={
                lower_map["time"]: "time",
                lower_map["group"]: "group",
                lower_map["value"]: "value",
            }
        )
        if "replicate" in cols_lower:
            df = df.rename(columns={lower_map["replicate"]: "replicate"})
        else:
            df["replicate"] = "R1"

        df["time"] = _coerce_time(df["time"])
        df["group"] = df["group"].astype(str)
        df["replicate"] = df["replicate"].astype(str)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["time", "value"])
        return df[["time", "group", "replicate", "value"]].reset_index(drop=True)

    raise ValueError(
        "Cannot detect format. Need: wide (time + group columns), "
        "tidy (time, group, value), or Incucyte TXT export."
    )


def aggregate_stats(df: pd.DataFrame, interval_hours: float = None) -> pd.DataFrame:
    d = df.copy()
    if interval_hours is not None and interval_hours > 0:
        d["time_bin"] = (np.floor(d["time"] / interval_hours) * interval_hours).astype(float)
        time_col = "time_bin"
    else:
        time_col = "time"

    stats = (
        d.groupby(["group", time_col], as_index=False)["value"]
        .agg(mean="mean", sd="std", n="count")
    )
    stats = stats.rename(columns={time_col: "time"})
    stats["sd"] = stats["sd"].fillna(0.0)
    stats["sem"] = stats["sd"] / np.sqrt(stats["n"].clip(lower=1))
    return stats


# ─────────────────────────────────────────────
#  Professional color palette
# ─────────────────────────────────────────────
PALETTE = [
    "#00c9a7", "#3b82f6", "#f59e0b", "#ef4444", "#a78bfa",
    "#f472b6", "#34d399", "#60a5fa", "#fbbf24", "#f87171",
    "#c084fc", "#fb7185", "#6ee7b7", "#93c5fd", "#fcd34d",
    "#fca5a5", "#d8b4fe", "#fda4af", "#86efac", "#bfdbfe",
]

DASH_PATTERNS = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot"]


def get_dash(i: int, use_dash: bool) -> str:
    return DASH_PATTERNS[i % len(DASH_PATTERNS)] if use_dash else "solid"


def make_color_list(n: int) -> list[str]:
    repeats = (n + len(PALETTE) - 1) // len(PALETTE)
    return (PALETTE * repeats)[:n]


# ─────────────────────────────────────────────
#  Plotly theme — cleaner for export + Streamlit
# ─────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(family="Arial, Helvetica, sans-serif", color="#111827", size=14),
    xaxis=dict(
        showline=True,
        linewidth=1.2,
        linecolor="#374151",
        mirror=False,
        ticks="outside",
        tickwidth=1.0,
        tickcolor="#374151",
        ticklen=5,
        showgrid=True,
        gridcolor="#e5e7eb",
        gridwidth=0.8,
        zeroline=False,
        title_font=dict(size=15, color="#111827"),
        tickfont=dict(size=12, color="#374151"),
    ),
    yaxis=dict(
        showline=True,
        linewidth=1.2,
        linecolor="#374151",
        mirror=False,
        ticks="outside",
        tickwidth=1.0,
        tickcolor="#374151",
        ticklen=5,
        showgrid=True,
        gridcolor="#e5e7eb",
        gridwidth=0.8,
        zeroline=False,
        title_font=dict(size=15, color="#111827"),
        tickfont=dict(size=12, color="#374151"),
    ),
    hovermode="x unified",
)


def save_figure_bytes(fig_plotly, fmt="png", dpi=300, width_in=6.9, height_in=4.8):
    """
    Export Plotly figure to bytes with explicit output dimensions.
    Raster formats use inch × dpi sizing.
    Vector formats also get explicit dimensions so text/layout are consistent.
    """
    fmt = fmt.lower()

    export_fig = go.Figure(fig_plotly)
    export_fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    if fmt in ("png", "jpg", "jpeg", "tif", "tiff"):
        width_px = max(1, int(round(width_in * dpi)))
        height_px = max(1, int(round(height_in * dpi)))
    else:
        vector_ref_dpi = 300
        width_px = max(1, int(round(width_in * vector_ref_dpi)))
        height_px = max(1, int(round(height_in * vector_ref_dpi)))

    if fmt in ("tif", "tiff"):
        png_bytes = pio.to_image(
            export_fig,
            format="png",
            width=width_px,
            height=height_px,
            scale=1,
            engine="kaleido",
        )
        from PIL import Image
        img = Image.open(io.BytesIO(png_bytes))
        buf = io.BytesIO()
        img.save(buf, format="TIFF", dpi=(dpi, dpi))
        buf.seek(0)
        return buf

    actual_fmt = "jpeg" if fmt == "jpg" else fmt
    buf = io.BytesIO(
        pio.to_image(
            export_fig,
            format=actual_fmt,
            width=width_px,
            height=height_px,
            scale=1,
            engine="kaleido",
        )
    )
    buf.seek(0)
    return buf


def get_download_mime(fmt: str) -> str:
    return {
        "png": "image/png",
        "pdf": "application/pdf",
        "svg": "image/svg+xml",
        "tif": "image/tiff",
        "tiff": "image/tiff",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }.get(fmt.lower(), "application/octet-stream")


# ─────────────────────────────────────────────
#  Header
# ─────────────────────────────────────────────
st.markdown("""
<div style="padding: 28px 0 8px 0; border-bottom: 1px solid #e2e8f0; margin-bottom: 24px;">
    <div class="hero-title">🔬 Incucyte <span class="hero-accent">Timecourse</span> Plotter</div>
    <div class="hero-sub">Live-cell imaging analysis · Mean ± SEM/SD · Publication-ready export</div>
    <div style="margin-top:12px;">
        <span class="badge">CSV / TXT / TSV</span>
        <span class="badge">Incucyte TXT Export</span>
        <span class="badge">Manual Entry</span>
        <span class="badge">PNG / PDF / SVG / TIFF</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace; font-size:0.7rem; letter-spacing:0.15em;
         text-transform:uppercase; color:#64748b; border-bottom:1px solid #e2e8f0;
         padding-bottom:6px; margin-bottom:16px;">
    ⚙ Plot Settings
    </div>
    """, unsafe_allow_html=True)

    x_label = st.text_input("X axis label", value="Time (h)")
    y_label = st.text_input("Y axis label", value="Confluence (%)")

    st.markdown("---")

    error_choice = st.selectbox("Error band", ["SEM", "SD", "None"], index=0)
    interval = st.number_input("Time binning (hours, 0 = off)", min_value=0.0, value=0.0, step=1.0)
    interval_hours = interval if interval > 0 else None

    smooth_step = st.number_input(
        "Plot every Nth point",
        min_value=1,
        value=1,
        step=1,
        help="1 = all points; 2 = every 2nd; etc.",
    )

    show_replicates = st.checkbox("Overlay faint replicate lines", value=False)

    st.markdown("---")

    band_alpha = st.slider("Error band opacity", 0.05, 0.6, 0.18, 0.01)
    line_width = st.slider("Line width", 1.0, 5.0, 2.5, 0.5)
    line_opacity = st.slider(
        "Line opacity",
        0.2,
        1.0,
        1.0,
        0.05,
        help="Reduce to see overlapping lines through each other",
    )

    use_dash_patterns = st.checkbox(
        "Distinct dash patterns per group",
        value=True,
        help="Solid, dashed, dotted, dash-dot — helps distinguish overlapping lines",
    )

    show_markers = st.checkbox("Show data point markers", value=False)
    marker_size = st.slider("Marker size", 3, 12, 6, 1) if show_markers else 6

    st.markdown("---")

    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace; font-size:0.7rem; letter-spacing:0.15em;
         text-transform:uppercase; color:#64748b; margin-bottom:10px;">
    📦 Export
    </div>
    """, unsafe_allow_html=True)

    export_format = st.selectbox("Format", ["PNG", "PDF", "SVG", "TIFF"], index=0)
    export_dpi = st.selectbox(
        "Raster DPI",
        [150, 300, 600, 1200],
        index=1,
        help="Applies to PNG and TIFF. PDF and SVG are vector.",
    )

    st.markdown("---")
    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace; font-size:0.68rem; letter-spacing:0.15em;
         text-transform:uppercase; color:#64748b; margin-bottom:10px;">
    📐 Figure size
    </div>
    """, unsafe_allow_html=True)

    figure_preset = st.selectbox(
        "Preset",
        ["Custom", "Screen", "Presentation", "Publication single-column", "Publication double-column"],
        index=3,
    )

    preset_dims = {
        "Custom": (8.0, 5.5),
        "Screen": (10.0, 6.0),
        "Presentation": (11.0, 6.5),
        "Publication single-column": (3.35, 2.8),
        "Publication double-column": (6.9, 5.2),
    }
    default_w, default_h = preset_dims[figure_preset]
    fig_width = st.number_input("Width (inches)", min_value=2.0, max_value=20.0, value=float(default_w), step=0.1)
    fig_height = st.number_input("Height (inches)", min_value=2.0, max_value=20.0, value=float(default_h), step=0.1)

    st.markdown("---")
    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace; font-size:0.68rem; letter-spacing:0.15em;
         text-transform:uppercase; color:#64748b; margin-bottom:10px;">
    🔲 Axis controls
    </div>
    """, unsafe_allow_html=True)

    with st.expander("X axis", expanded=False):
        x_scale = st.selectbox("Scale", ["linear", "log"], index=0, key="x_scale")
        x_auto = st.checkbox("Auto range", value=True, key="x_auto")
        x_min = st.number_input("X min", value=0.0, step=1.0, key="x_min", disabled=x_auto)
        x_max = st.number_input("X max", value=100.0, step=1.0, key="x_max", disabled=x_auto)
        x_dtick = st.number_input(
            "Tick interval (0 = auto)",
            value=0.0,
            step=1.0,
            key="x_dtick",
            help="e.g. 24 to show ticks every 24 h",
        )

    with st.expander("Y axis", expanded=False):
        y_scale = st.selectbox("Scale", ["linear", "log"], index=0, key="y_scale")
        y_auto = st.checkbox("Auto range", value=True, key="y_auto")
        y_min = st.number_input("Y min", value=0.0, step=1.0, key="y_min", disabled=y_auto)
        y_max = st.number_input("Y max", value=100.0, step=1.0, key="y_max", disabled=y_auto)
        y_dtick = st.number_input(
            "Tick interval (0 = auto)",
            value=0.0,
            step=1.0,
            key="y_dtick",
            help="e.g. 20 to show ticks every 20 %",
        )

# ─────────────────────────────────────────────
#  Data input
# ─────────────────────────────────────────────
input_mode = st.radio(
    "Data source",
    ["📂  Upload file", "✏️  Enter manually"],
    horizontal=True,
    label_visibility="collapsed",
)

tidy = None

if input_mode == "📂  Upload file":
    uploaded = st.file_uploader(
        "Drag & drop a CSV, TSV, or Incucyte TXT export",
        type=["csv", "txt", "tsv"],
        label_visibility="collapsed",
    )
    if uploaded is not None:
        try:
            tidy = read_incucyte_csv(uploaded)
        except Exception as e:
            st.error(f"**Parse error:** {e}")
            st.stop()
    else:
        st.markdown("""
        <div style="background:#f8fafc; border:1.5px dashed #cbd5e1; border-radius:8px;
             padding:28px; text-align:center; color:#64748b; font-size:0.88rem;">
        Upload a <strong style="color:#3b82f6">CSV / TSV</strong> or
        <strong style="color:#00c9a7">Incucyte TXT</strong> export above to begin.
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown('<p class="section-header">Manual data entry</p>', unsafe_allow_html=True)
    starter = pd.DataFrame({
        "time": [0.0, 0.0, 2.0, 2.0],
        "group": ["Control", "DrugA", "Control", "DrugA"],
        "replicate": ["R1", "R1", "R1", "R1"],
        "value": [np.nan, np.nan, np.nan, np.nan],
    })
    edited = st.data_editor(starter, num_rows="dynamic", use_container_width=True, key="editor")
    edited["time"] = pd.to_numeric(edited["time"], errors="coerce")
    edited["value"] = pd.to_numeric(edited["value"], errors="coerce")
    edited["group"] = edited["group"].astype(str)
    edited["replicate"] = edited["replicate"].astype(str)
    tidy = edited.dropna(subset=["time", "value"]).reset_index(drop=True)
    if tidy.empty:
        st.info("Fill in time + value rows to generate plots.")

# ─────────────────────────────────────────────
#  Main dashboard
# ─────────────────────────────────────────────
if tidy is not None and not tidy.empty:
    groups = pd.unique(tidy["group"].astype(str)).tolist()
    default_colors = make_color_list(len(groups))

    with st.sidebar:
        st.markdown("""
        <div style="font-family:'IBM Plex Mono',monospace; font-size:0.7rem; letter-spacing:0.15em;
             text-transform:uppercase; color:#64748b; border-top:1px solid #e2e8f0;
             padding-top:12px; margin-top:4px; margin-bottom:10px;">
        🎨 Groups
        </div>
        """, unsafe_allow_html=True)

        name_map, color_map = {}, {}
        for i, g in enumerate(groups):
            with st.expander(f"{g}", expanded=False):
                name_map[g] = st.text_input("Display name", value=g, key=f"dn_{i}")
                color_map[g] = st.color_picker("Colour", value=default_colors[i], key=f"col_{i}")

    group_df = pd.DataFrame({
        "group": groups,
        "display_name": [name_map[g] for g in groups],
        "color": [color_map[g] for g in groups],
    })

    xaxis_extra = dict(type=x_scale)
    if not x_auto:
        xaxis_extra["range"] = [x_min, x_max]
    if x_dtick > 0:
        xaxis_extra["dtick"] = x_dtick
        xaxis_extra["tick0"] = 0

    yaxis_extra = dict(type=y_scale)
    if not y_auto:
        yaxis_extra["range"] = [y_min, y_max]
    if y_dtick > 0:
        yaxis_extra["dtick"] = y_dtick
        yaxis_extra["tick0"] = 0

    try:
        import kaleido  # noqa: F401
        _test_fig = go.Figure(go.Scatter(x=[0], y=[0]))
        _test_fig.to_image(format="png", width=400, height=300, scale=1)
        _kaleido_ok = True
        _kaleido_error = None
    except Exception as e:
        _kaleido_ok = False
        _kaleido_error = str(e)

    stats = aggregate_stats(tidy, interval_hours=interval_hours)
    stats = stats.merge(group_df, on="group", how="left", validate="many_to_one")
    tidy_m = tidy.merge(group_df, on="group", how="left", validate="many_to_one")

    error_col = {"SD": "sd", "SEM": "sem"}.get(error_choice, None)

    n_groups = len(groups)
    reps_per_group = tidy.groupby("group")["replicate"].nunique()
    typical_reps = int(reps_per_group.median()) if not reps_per_group.empty else 0
    t_min, t_max = tidy["time"].min(), tidy["time"].max()
    n_timepoints = tidy["time"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    for col, label, val, sub in [
        (c1, "Groups", n_groups, "conditions"),
        (c2, "Replicates", typical_reps, "median per group"),
        (c3, "Timepoints", n_timepoints, f"{t_min:.0f} – {t_max:.0f} h"),
        (c4, "Observations", len(tidy), "total rows"),
    ]:
        col.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{val}</div>
            <div class="metric-sub">{sub}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📈  Mean ± Error",
        "🍝  Replicate Spaghetti",
        "📋  Data Table",
        "📊  Summary Stats",
    ])

    # ─── TAB 1: Mean ± Error ───────────────────────────────────
    with tab1:
        fig = go.Figure()

        for i, g in enumerate(groups):
            sub = stats[stats["group"] == g].sort_values("time")
            if smooth_step > 1:
                sub = sub.iloc[::smooth_step]

            name = group_df.loc[group_df["group"] == g, "display_name"].values[0]
            color = group_df.loc[group_df["group"] == g, "color"].values[0]
            dash = get_dash(i, use_dash_patterns)
            r_c, g_c, b_c = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)

            if show_replicates:
                for _, rsub in tidy_m[tidy_m["group"] == g].groupby("replicate"):
                    rsub = rsub.sort_values("time")
                    if smooth_step > 1:
                        rsub = rsub.iloc[::smooth_step]
                    fig.add_trace(go.Scatter(
                        x=rsub["time"],
                        y=rsub["value"],
                        mode="lines",
                        line=dict(color=color, width=1.0, dash=dash),
                        opacity=0.18,
                        showlegend=False,
                        hoverinfo="skip",
                    ))

            if error_col and sub[error_col].notna().any():
                y_upper = sub["mean"] + sub[error_col]
                y_lower = sub["mean"] - sub[error_col]
                fill_color = f"rgba({r_c},{g_c},{b_c},{band_alpha})"
                fig.add_trace(go.Scatter(
                    x=pd.concat([sub["time"], sub["time"][::-1]]),
                    y=pd.concat([y_upper, y_lower[::-1]]),
                    fill="toself",
                    fillcolor=fill_color,
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                    name=f"{name} band",
                ))

            mode = "lines+markers" if show_markers else "lines"
            fig.add_trace(go.Scatter(
                x=sub["time"],
                y=sub["mean"],
                mode=mode,
                name=name,
                opacity=line_opacity,
                line=dict(color=color, width=line_width, dash=dash),
                marker=dict(
                    symbol="circle",
                    size=marker_size,
                    color=color,
                    line=dict(color="white", width=1.2),
                ) if show_markers else dict(size=0),
                hovertemplate=f"<b>{name}</b><br>{x_label}: %{{x}}<br>{y_label}: %{{y:.2f}}<extra></extra>",
            ))

        error_label = f" ± {error_choice}" if error_col else ""
        plot_height_px = max(int(fig_height * 96), 520)

        fig.update_layout(
            **PLOTLY_LAYOUT,
            xaxis_title=x_label,
            yaxis_title=y_label,
            title=dict(text=f"Mean{error_label} per group", font=dict(size=15, color="#374151"), x=0),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.28,
                xanchor="left",
                x=0,
                bgcolor="rgba(255,255,255,0.92)",
                bordercolor="#d1d5db",
                borderwidth=1,
                font=dict(size=12, color="#111827"),
                title_text="",
            ),
            width=int(fig_width * 96),
            height=plot_height_px,
            margin=dict(l=70, r=25, t=60, b=150),
        )
        fig.update_xaxes(**xaxis_extra)
        fig.update_yaxes(**yaxis_extra)

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displaylogo": False,
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": "incucyte_mean_plot",
                    "height": int(fig_height * 300),
                    "width": int(fig_width * 300),
                    "scale": 1,
                },
                "modeBarButtonsToRemove": [
                    "lasso2d",
                    "select2d",
                    "autoScale2d",
                ],
            },
        )

        fmt = export_format.lower()
        if fmt == "tiff":
            fmt = "tif"
        is_vector = fmt in ("pdf", "svg")
        label_dpi = "vector" if is_vector else f"{export_dpi} dpi"

        if not _kaleido_ok:
            st.info(
                "Static export buttons are unavailable in this Streamlit deployment. "
                "Use the camera icon in the chart toolbar to export a high-resolution PNG."
            )
            with st.expander("Technical details"):
                st.code(_kaleido_error or "Unknown Kaleido error")
        else:
            st.markdown("""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;
                 letter-spacing:0.1em;text-transform:uppercase;color:#64748b;
                 margin:12px 0 6px;">⬇ Export mean plot</div>
            """, unsafe_allow_html=True)

            dc1, dc2, dc3, dc4 = st.columns(4)
            with dc1:
                st.download_button(
                    f"✦ {export_format} · {label_dpi}",
                    data=save_figure_bytes(fig, fmt, dpi=export_dpi, width_in=fig_width, height_in=fig_height),
                    file_name=f"mean_plot_{export_dpi}dpi.{fmt}",
                    mime=get_download_mime(fmt),
                    use_container_width=True,
                )
            with dc2:
                st.download_button(
                    "PNG · 300 dpi",
                    data=save_figure_bytes(fig, "png", dpi=300, width_in=fig_width, height_in=fig_height),
                    file_name="mean_plot_300dpi.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with dc3:
                st.download_button(
                    "PNG · 600 dpi",
                    data=save_figure_bytes(fig, "png", dpi=600, width_in=fig_width, height_in=fig_height),
                    file_name="mean_plot_600dpi.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with dc4:
                st.download_button(
                    "PDF · vector",
                    data=save_figure_bytes(fig, "pdf", dpi=export_dpi, width_in=fig_width, height_in=fig_height),
                    file_name="mean_plot.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

    # ─── TAB 2: Spaghetti ─────────────────────────────────────
    with tab2:
        fig2 = go.Figure()
        added_legend = set()

        for i, g in enumerate(groups):
            name = group_df.loc[group_df["group"] == g, "display_name"].values[0]
            color = group_df.loc[group_df["group"] == g, "color"].values[0]
            dash = get_dash(i, use_dash_patterns)
            r_c, g_c, b_c = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)

            for rep, rsub in tidy_m[tidy_m["group"] == g].groupby("replicate"):
                rsub = rsub.sort_values("time")
                if smooth_step > 1:
                    rsub = rsub.iloc[::smooth_step]
                show = name not in added_legend
                mode = "lines+markers" if show_markers else "lines"

                fig2.add_trace(go.Scatter(
                    x=rsub["time"],
                    y=rsub["value"],
                    mode=mode,
                    name=name,
                    legendgroup=name,
                    showlegend=show,
                    opacity=line_opacity,
                    line=dict(color=f"rgba({r_c},{g_c},{b_c},1)", width=1.8, dash=dash),
                    marker=dict(
                        symbol="circle",
                        size=max(3, marker_size - 1),
                        color=color,
                        line=dict(color="white", width=1),
                    ) if show_markers else dict(size=0),
                    hovertemplate=f"<b>{name}</b> [{rep}]<br>{x_label}: %{{x}}<br>{y_label}: %{{y:.2f}}<extra></extra>",
                ))
                added_legend.add(name)

        plot_height_px2 = max(int(fig_height * 96), 520)

        fig2.update_layout(
            **PLOTLY_LAYOUT,
            xaxis_title=x_label,
            yaxis_title=y_label,
            title=dict(text="Individual replicates (spaghetti)", font=dict(size=15, color="#374151"), x=0),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.28,
                xanchor="left",
                x=0,
                bgcolor="rgba(255,255,255,0.92)",
                bordercolor="#d1d5db",
                borderwidth=1,
                font=dict(size=12, color="#111827"),
                title_text="",
            ),
            width=int(fig_width * 96),
            height=plot_height_px2,
            margin=dict(l=70, r=25, t=60, b=150),
        )
        fig2.update_xaxes(**xaxis_extra)
        fig2.update_yaxes(**yaxis_extra)

        st.plotly_chart(
            fig2,
            use_container_width=True,
            config={
                "displaylogo": False,
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": "incucyte_spaghetti_plot",
                    "height": int(fig_height * 300),
                    "width": int(fig_width * 300),
                    "scale": 1,
                },
                "modeBarButtonsToRemove": [
                    "lasso2d",
                    "select2d",
                    "autoScale2d",
                ],
            },
        )

        if _kaleido_ok:
            st.markdown("""
            <div style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;
                 letter-spacing:0.1em;text-transform:uppercase;color:#64748b;
                 margin:12px 0 6px;">⬇ Export spaghetti plot</div>
            """, unsafe_allow_html=True)

            dc1, dc2, dc3, dc4 = st.columns(4)
            with dc1:
                st.download_button(
                    f"✦ {export_format} · {label_dpi}",
                    data=save_figure_bytes(fig2, fmt, dpi=export_dpi, width_in=fig_width, height_in=fig_height),
                    file_name=f"spaghetti_{export_dpi}dpi.{fmt}",
                    mime=get_download_mime(fmt),
                    use_container_width=True,
                )
            with dc2:
                st.download_button(
                    "PNG · 300 dpi",
                    data=save_figure_bytes(fig2, "png", dpi=300, width_in=fig_width, height_in=fig_height),
                    file_name="spaghetti_300dpi.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with dc3:
                st.download_button(
                    "PNG · 600 dpi",
                    data=save_figure_bytes(fig2, "png", dpi=600, width_in=fig_width, height_in=fig_height),
                    file_name="spaghetti_600dpi.png",
                    mime="image/png",
                    use_container_width=True,
                )
            with dc4:
                st.download_button(
                    "SVG · vector",
                    data=save_figure_bytes(fig2, "svg", dpi=export_dpi, width_in=fig_width, height_in=fig_height),
                    file_name="spaghetti.svg",
                    mime="image/svg+xml",
                    use_container_width=True,
                )
        else:
            st.info("Use the camera icon in the chart toolbar to export the spaghetti plot as PNG.")

    # ─── TAB 3: Raw data ──────────────────────────────────────
    with tab3:
        st.markdown('<p class="section-header">Parsed tidy data</p>', unsafe_allow_html=True)
        st.dataframe(tidy, use_container_width=True, height=400)

        csv_raw = tidy.to_csv(index=False)
        st.download_button(
            "⬇ Download tidy data CSV",
            data=csv_raw,
            file_name="tidy_data.csv",
            mime="text/csv",
        )

    # ─── TAB 4: Summary stats ─────────────────────────────────
    with tab4:
        st.markdown('<p class="section-header">Aggregated statistics</p>', unsafe_allow_html=True)

        display_stats = (
            stats[["display_name", "time", "mean", "sd", "sem", "n"]]
            .rename(columns={
                "display_name": "group",
                "mean": "Mean",
                "sd": "SD",
                "sem": "SEM",
                "n": "N",
            })
            .sort_values(["group", "time"])
            .reset_index(drop=True)
        )
        display_stats = display_stats.round(4)

        st.dataframe(display_stats, use_container_width=True, height=400)

        csv_buf = io.StringIO()
        stats.to_csv(csv_buf, index=False)
        st.download_button(
            "⬇ Download summary CSV",
            data=csv_buf.getvalue(),
            file_name="summary_mean_sd_sem.csv",
            mime="text/csv",
        )

    st.markdown("""
    <div style="margin-top:40px; padding-top:16px; border-top:1px solid #e2e8f0;
         font-family:'IBM Plex Mono',monospace; font-size:0.68rem; color:#94a3b8;
         text-align:center; letter-spacing:0.08em;">
    INCUCYTE TIMECOURSE PLOTTER · Live-cell imaging analysis
    </div>
    """, unsafe_allow_html=True)
