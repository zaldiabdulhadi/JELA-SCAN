
import os
import pandas as pd
import streamlit as st
import plotly.express as px

from streamlit_autorefresh import st_autorefresh

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Jelantah Scanner",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

CSV_FILE = "data/sensor_data.csv"

st_autorefresh(
    interval=5000,
    key="dashboard_refresh"
)

# ==========================================
# 2. COMPACT CSS
# ==========================================

st.markdown("""
<style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0.5rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 100%;
    }

    header[data-testid="stHeader"] {
        height: 0rem;
    }

    #MainMenu, footer {
        visibility: hidden;
    }

    h1 {
        font-size: 1.65rem !important;
        padding-bottom: 0rem !important;
    }

    h2 {
        font-size: 1.05rem !important;
        padding-bottom: 0rem !important;
    }

    h3 {
        font-size: 0.95rem !important;
    }

    [data-testid="stMetric"] {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,0.15);
        padding: 10px 12px;
        border-radius: 10px;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.75rem;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }

    div[data-testid="stVerticalBlock"] {
        gap: 0.65rem;
    }

    div[data-testid="stPlotlyChart"] {
        margin-bottom: -15px;
    }

    .status-text {
        font-size: 0.78rem;
        color: gray;
    }

    .grade-card {
        background: var(--secondary-background-color);
        border-radius: 12px;
        padding: 15px;
        border: 1px solid rgba(128,128,128,0.15);
        min-height: 155px;
    }

    .grade-value {
        font-size: 2.5rem;
        font-weight: 750;
        margin: 3px 0;
    }

    .small-label {
        font-size: 0.75rem;
        color: gray;
    }

    .route-value {
        font-size: 1.15rem;
        font-weight: 650;
    }

    hr {
        margin: 0.35rem 0 !important;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 3. LOAD DATA
# ==========================================

@st.cache_data(ttl=2)
def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_FILE)

        if df.empty:
            return df

        df["received_at"] = pd.to_datetime(
            df["received_at"],
            errors="coerce",
            utc=True
        )

        numeric_columns = [
            "temp_c",
            "moisture_pct",
            "turbidity_ntu",
            "color_bright",
            "yield_pct",
            "price_rp"
        ]

        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

        return df.sort_values("received_at")

    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


df = load_data()


# ==========================================
# 4. HEADER
# ==========================================

header_left, header_right = st.columns([3, 1])

with header_left:
    st.markdown(
        "<h1>🛢️ JELANTAH SCANNER</h1>",
        unsafe_allow_html=True
    )

with header_right:
    st.markdown(
        "<div style='text-align:right; padding-top:10px;'>"
        "<span style='color:#16A34A;font-weight:650;'>● LIVE MONITORING</span>"
        "</div>",
        unsafe_allow_html=True
    )

st.divider()

if df.empty:
    st.warning(
        "Belum ada data sensor. "
        "Pastikan MQTT Subscriber sedang berjalan."
    )
    st.stop()


latest = df.iloc[-1]


# ==========================================
# 5. DEVICE STATUS
# ==========================================

last_time = latest["received_at"]

if pd.notna(last_time):
    now = pd.Timestamp.now(tz="UTC")
    age_seconds = (now - last_time).total_seconds()
else:
    age_seconds = None

device_online = (
    age_seconds is not None
    and 0 <= age_seconds <= 30
)

status_color = "#16A34A" if device_online else "#DC2626"
status_label = "ONLINE" if device_online else "OFFLINE / STALE"

st.markdown(
    f"<div class='status-text'>"
    f"DEVICE: <b>{latest.get('device', '-')}</b>"
    f" &nbsp; | &nbsp; "
    f"STATUS: <span style='color:{status_color};font-weight:700;'>"
    f"{status_label}</span>"
    f" &nbsp; | &nbsp; "
    f"TOTAL SCANS: <b>{len(df):,}</b>"
    f"</div>",
    unsafe_allow_html=True
)


# ==========================================
# 6. SENSOR METRICS
# ==========================================

st.markdown("### Sensor Readings")

c1, c2, c3, c4 = st.columns(4)

sensor_metrics = [
    ("Temperature", "temp_c", "°C"),
    ("Moisture", "moisture_pct", "%"),
    ("Turbidity", "turbidity_ntu", ""),
    ("Color Brightness", "color_bright", "")
]

for col, (label, field, unit) in zip(
    [c1, c2, c3, c4],
    sensor_metrics
):
    value = latest.get(field)

    if pd.notna(value):
        formatted = f"{value:.2f} {unit}".strip()
    else:
        formatted = "-"

    col.metric(label, formatted)


# ==========================================
# 7. QUALITY ASSESSMENT + CHART
# ==========================================

st.divider()

left, right = st.columns([1, 1.65], gap="medium")

grade = str(latest.get("grade", "-"))
status = str(latest.get("status", "-"))
route = str(latest.get("route", "-"))

grade_colors = {
    "A": "#16A34A",
    "B": "#D69E36",
    "C": "#EA580C",
    "REJECT": "#DC2626"
}

grade_color = grade_colors.get(grade, "#64748B")

with left:
    st.markdown("### Quality Assessment")

    st.markdown(
        f"""
        <div class="grade-card">
            <div class="small-label">CURRENT CLASSIFICATION</div>
            <div class="grade-value" style="color:{grade_color};">
                {grade}
            </div>
            <div style="font-size:0.85rem;">{status}</div>
            <hr>
            <div class="small-label">RECOMMENDED ROUTE</div>
            <div class="route-value">{route}</div>
            <div class="small-label">
                Estimated Yield: {latest.get('yield_pct', '-')}%
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.caption(
        "Hasil klasifikasi berbasis aturan ESP32, "
        "bukan prediksi Machine Learning."
    )

with right:
    st.markdown("### Sensor Trend")

    sensor_options = {
        "Temperature": "temp_c",
        "Moisture": "moisture_pct",
        "Turbidity": "turbidity_ntu",
        "Color Brightness": "color_bright"
    }

    selected_sensor = st.selectbox(
        "Parameter",
        list(sensor_options.keys()),
        label_visibility="collapsed"
    )

    selected_column = sensor_options[selected_sensor]

    chart_data = df[
        ["received_at", selected_column]
    ].dropna().tail(30)

    if not chart_data.empty:
        fig = px.line(
            chart_data,
            x="received_at",
            y=selected_column,
            markers=True
        )

        fig.update_layout(
            template="plotly_white",
            height=205,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title=None,
            yaxis_title=None,
            showlegend=False,
            font=dict(size=10)
        )

        fig.update_traces(
            line=dict(width=2),
            marker=dict(size=5)
        )

        fig.update_xaxes(
            showgrid=False,
            tickfont=dict(size=9)
        )

        fig.update_yaxes(
            gridcolor="rgba(128,128,128,0.15)",
            tickfont=dict(size=9)
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={"displayModeBar": False}
        )
    else:
        st.info("Data sensor belum tersedia.")


# ==========================================
# 8. DISTRIBUTION + LATEST HISTORY
# ==========================================

st.divider()

bottom_left, bottom_right = st.columns(
    [1, 1.65],
    gap="medium"
)

with bottom_left:
    st.markdown("### Grade Distribution")

    if "grade" in df.columns:
        grade_counts = (
            df["grade"]
            .fillna("Unknown")
            .value_counts()
            .rename_axis("Grade")
            .reset_index(name="Total")
        )

        fig_grade = px.bar(
            grade_counts,
            x="Grade",
            y="Total",
            color="Grade",
            text="Total",
            color_discrete_map=grade_colors
        )

        fig_grade.update_layout(
            template="plotly_white",
            height=175,
            margin=dict(l=5, r=5, t=10, b=5),
            showlegend=False,
            xaxis_title=None,
            yaxis_title=None,
            font=dict(size=10)
        )

        fig_grade.update_traces(
            textposition="outside"
        )

        st.plotly_chart(
            fig_grade,
            use_container_width=True,
            config={"displayModeBar": False}
        )

with bottom_right:
    st.markdown("### Latest Measurement History")

    display_columns = [
        "received_at",
        "temp_c",
        "moisture_pct",
        "turbidity_ntu",
        "color_bright",
        "grade",
        "route"
    ]

    available_columns = [
        col for col in display_columns
        if col in df.columns
    ]

    history = df[available_columns].tail(5).copy()

    if "received_at" in history.columns:
        history["received_at"] = (
            history["received_at"]
            .dt.strftime("%H:%M:%S")
        )

    st.dataframe(
        history.iloc[::-1],
        use_container_width=True,
        hide_index=True,
        height=175
    )


# ==========================================
# 9. FOOTER
# ==========================================

st.divider()

footer_left, footer_right = st.columns(2)

with footer_left:
    st.caption(
        "Jelantah Scanner | IoT Monitoring Dashboard"
    )

with footer_right:
    st.caption(
        "Auto-refresh: 5 seconds | Latest 30 readings in chart"
    )