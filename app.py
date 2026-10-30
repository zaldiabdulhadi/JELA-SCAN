import os
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

# host/port command diambil dari subscriber agar satu sumber kebenaran
# (mqtt_client punya guard __main__, jadi import ini TIDAK auto-connect)
from mqtt_client import MQTT_HOST, MQTT_PORT

# 1. PAGE CONFIGURATION
st.set_page_config(
    page_title="Jelantah Scanner",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "data", "sensor_data.csv")
st_autorefresh(interval=5000, key="dashboard_refresh")

# 2. DESIGN SYSTEM 
st.markdown("""
<style>
    /* font & warna SEMANTIK saja yang di-hardcode (aman 2 tema).
       Warna teks NETRAL & latar TIDAK disentuh -> warisi dari Streamlit. */
    :root{
        --gA:#16A34A; --gB:#D97706; --gC:#EA580C; --gR:#DC2626; --gX:#94A3B8;
        --line: rgba(128,128,128,0.22);          /* border universal */
        --surface: rgba(128,128,128,0.08);       /* panel: naik di gelap, turun di terang */
        --mono: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
        --sans: "Segoe UI", system-ui, -apple-system, sans-serif;
    }
    .block-container{
        padding-top:1.1rem; padding-bottom:0.6rem;
        padding-left:2.2rem; padding-right:2.2rem; max-width:100%;
        font-family:var(--sans);                 /* TANPA color -> inherit */
    }
    header[data-testid="stHeader"]{height:0rem;}
    #MainMenu, footer{visibility:hidden;}

    h1{font-size:1.95rem !important; font-weight:700; letter-spacing:-0.02em;
       margin:0 !important; line-height:1.1;}
    h2{font-size:1.05rem !important; font-weight:600; margin:0 !important;}
    h3{font-size:0.72rem !important; font-weight:700; letter-spacing:0.09em;
       text-transform:uppercase; opacity:.6; margin:0 0 .35rem 0 !important;}

    [data-testid="stMetric"]{background:transparent; border:0; padding:2px 0; border-radius:0;}
    [data-testid="stMetricLabel"]{font-size:0.68rem; letter-spacing:0.06em;
        text-transform:uppercase; opacity:.6;}
    [data-testid="stMetricValue"]{font-family:var(--mono); font-variant-numeric:tabular-nums;
        font-size:1.3rem; font-weight:600;}
    [data-testid="stMetricDelta"]{font-family:var(--mono);}

    div[data-testid="stVerticalBlock"]{gap:0.7rem;}
    div[data-testid="stPlotlyChart"]{margin-bottom:-12px;}

    .panel{background:var(--surface); border:1px solid var(--line);
           border-radius:4px; padding:14px 16px;}
    .panel .lbl{font-size:0.66rem; letter-spacing:0.08em; text-transform:uppercase; opacity:.6;}
    .panel .big{font-family:var(--mono); font-variant-numeric:tabular-nums;
                font-size:2.4rem; font-weight:700; line-height:1; margin:4px 0;}
                /* warna .big diset INLINE per-grade (semantik) -> jangan timpa di sini */
    .panel .sub{font-size:0.82rem;}
    .panel .meta{font-family:var(--mono); font-size:0.78rem; opacity:.7;
                 margin-top:6px; padding-top:6px; border-top:1px solid var(--line);}

    .dot{display:inline-block; width:8px; height:8px; border-radius:50%;
         margin-right:6px; vertical-align:middle;}
    .dot.on{background:var(--gA);} .dot.off{background:var(--gR);}
    .status-line{font-size:0.74rem; opacity:.85; font-family:var(--mono);}
    .status-line b{font-weight:600;}
    hr{margin:0.4rem 0 !important; border-color:var(--line) !important;}
</style>
""", unsafe_allow_html=True)

# 3. LOAD DATA 
@st.cache_data(ttl=2)
def load_data():
    if not os.path.exists(CSV_FILE):
        return pd.DataFrame()
    try:
        df = pd.read_csv(CSV_FILE, on_bad_lines="skip")   # baris dengan jumlah kolom salah dilewati, bukan membunuh seluruh file
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    if df.empty:
        return df
    df["received_at"] = pd.to_datetime(df["received_at"], errors="coerce", utc=True)
    for col in ["temp_c","moisture_pct","turbidity_ntu","color_bright",
                "yield_pct","price_rp","iqk","confidence"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("received_at")

df = load_data()


# 4. HEADER 
header_left, header_right = st.columns([3, 1])
with header_left:
    st.markdown("<h1>JELANTAH SCANNER</h1>", unsafe_allow_html=True)
    st.markdown(
        "<div class='status-line'>Smart quality scanner &middot; "
        "jelantah&#8202;&#8594;&#8202;biodiesel &middot; ESP32 + MQTT</div>",
        unsafe_allow_html=True,
    )
with header_right:
    st.markdown(
        "<div style='text-align:right;padding-top:14px;'>"
        "<span class='dot on'></span>"
        "<span class='status-line'><b>LIVE</b></span></div>",
        unsafe_allow_html=True,
    )
st.divider()

if df.empty:
    st.warning(f"Belum ada data sensor di `{CSV_FILE}`. Pastikan `python mqtt_client.py` berjalan, lalu tekan tombol scan di Wokwi.")
    st.stop()

latest = df.iloc[-1]


# 5. DEVICE STATUS 
last_time = latest["received_at"]
age_seconds = (pd.Timestamp.now(tz="UTC") - last_time).total_seconds() if pd.notna(last_time) else None
online = age_seconds is not None and 0 <= age_seconds <= 30
dot_cls = "on" if online else "off"
state_txt = "ONLINE" if online else "OFFLINE / STALE"
st.markdown(
    f"<div class='status-line'><span class='dot {dot_cls}'></span>"
    f"DEVICE <b>{latest.get('device','-')}</b> &nbsp;|&nbsp; STATUS <b>{state_txt}</b> "
    f"&nbsp;|&nbsp; SCANS <b>{len(df):,}</b> &nbsp;|&nbsp; "
    f"LAST <b>{last_time.strftime('%H:%M:%S') if pd.notna(last_time) else '-'}</b></div>",
    unsafe_allow_html=True,
)

# 6. SENSOR METRICS 
st.markdown("### Sensor readings")
c1, c2, c3, c4 = st.columns(4)
for col, (label, field, unit) in zip(
    [c1, c2, c3, c4],
    [("Temperature","temp_c"," C"),("Moisture","moisture_pct"," %"),
     ("Turbidity","turbidity_ntu",""),("Color","color_bright","")],
):
    v = latest.get(field)
    col.metric(label, f"{v:.2f}{unit}".strip() if pd.notna(v) else "-")

# 7. QUALITY ASSESSMENT + IQK + CONFIDENCE  
st.divider()
left, right = st.columns([1, 1.65], gap="medium")

grade = str(latest.get("grade","-"))
status = str(latest.get("status","-"))
route = str(latest.get("route","-"))
GCOLOR = {"A":"var(--gA)","B":"var(--gB)","C":"var(--gC)","REJECT":"var(--gR)","HOLD":"var(--gX)"}
gcolor = GCOLOR.get(grade, "var(--gX)")

with left:
    st.markdown("### Classification")
    st.markdown(
        f"<div class='panel'>"
        f"<div class='lbl'>Current grade</div>"
        f"<div class='big' style='color:{gcolor}'>{grade}</div>"
        f"<div class='sub'>{status}</div>"
        f"<div class='meta'>ROUTE &nbsp;{route}<br>"
        f"YIELD &nbsp;{latest.get('yield_pct','-')}% &nbsp;&middot;&nbsp; "
        f"HARGA &nbsp;Rp{latest.get('price_rp',0):,}/L</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    # IQK sebagai gauge (data nyata, bukan sparkline hiasan)
    iqk = latest.get("iqk")
    if pd.notna(iqk):
        ic = "#16A34A" if iqk >= 70 else ("#D97706" if iqk >= 40 else "#DC2626")
        fig_iqk = go.Figure(go.Indicator(
            mode="gauge+number",
            value=float(iqk),
            number={"suffix": " / 100",
                    "font": {"size": 22, "family": "ui-monospace, monospace"}},
            gauge={
                "axis": {"range": [0, 100], "tickfont": {"size": 9}},
                "bar": {"color": ic},
                "steps": [
                    {"color": "rgba(220,38,38,0.12)", "range": [0, 40]},
                    {"color": "rgba(217,119,6,0.12)", "range": [40, 70]},
                    {"color": "rgba(22,163,74,0.12)", "range": [70, 100]},
                ],
            },
        ))
        fig_iqk.update_layout(
            height=118, margin=dict(l=0, r=0, t=22, b=0),
            template="plotly_white",
            title={"text": "Indeks Kualitas Komposit", "font": {"size": 11}},
            font={"family": "Segoe UI, system-ui", "size": 10},
        )
        st.plotly_chart(fig_iqk, use_container_width=True,
                        config={"displayModeBar": False})
    # confidence sebagai progress (bukan dekorasi)
    conf = latest.get("confidence")
    if pd.notna(conf):
        st.progress(min(float(conf)/100.0, 1.0), text=f"Keyakinan klasifikasi: {conf:.0f}%")
    st.caption("Klasifikasi berbasis aturan di ESP32; IQK & keyakinan adalah turunan deterministik, bukan prediksi ML.")

with right:
    st.markdown("### Sensor trend")
    opts = {"Temperature":"temp_c","Moisture":"moisture_pct",
            "Turbidity":"turbidity_ntu","Color":"color_bright"}
    sel = st.selectbox("Parameter", list(opts.keys()), label_visibility="collapsed")
    cd = df[["received_at", opts[sel]]].dropna().tail(30)
    if not cd.empty:
        fig = px.line(cd, x="received_at", y=opts[sel], markers=True)
        fig.update_layout(template="plotly_white", height=212,
                          margin=dict(l=8,r=8,t=8,b=8), xaxis_title=None, yaxis_title=None,
                          showlegend=False, font={"family":"Segoe UI, system-ui","size":10})
        fig.update_traces(line=dict(width=2, color="#0F172A"), marker=dict(size=5, color="#0F172A"))
        fig.update_xaxes(showgrid=False, tickfont=dict(size=9))
        fig.update_yaxes(gridcolor="rgba(15,23,42,0.08)", tickfont=dict(size=9, family="ui-monospace,monospace"))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})
    else:
        st.info("Data sensor belum tersedia.")

# 7.5. BUSINESS KPI (angka uang/liter yang dicari pengepul)
st.divider()
st.markdown("### Rekap transaksi")
SAMPLE_L = 1.0  # asumsi: 1 scan = 1 sampel 1 liter; sesuaikan prosedur kalian
bought = df[df["route"].isin(["A-Line","Pre-Tank"])] if "route" in df.columns else df
k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("Total scan", f"{len(df):,}")
k2.metric("Layak beli (A+B)", f"{len(bought):,}")
k3.metric("Ditolak / blocked", f"{len(df)-len(bought):,}")
k4.metric("Volume estimasi", f"{len(bought)*SAMPLE_L:,.1f} L")
k5.metric("Nilai beli (A+B)", f"Rp {bought['price_rp'].sum()*SAMPLE_L:,.0f}")
st.caption("Nilai hanya dijumlahkan untuk rute A-Line / Pre-Tank; C / REJECT / HOLD tidak masuk tangki beli.")

# 8. DISTRIBUTION + HISTORY
st.divider()
bl, br = st.columns([1, 1.65], gap="medium")
with bl:
    st.markdown("### Grade distribution")
    if "grade" in df.columns:
        gc = (df["grade"].fillna("Unknown").value_counts()
              .rename_axis("Grade").reset_index(name="Total"))
        cmap = {"A":"#15803D","B":"#B45309","C":"#C2410C","REJECT":"#B91C1C","HOLD":"#475569"}
        fg = px.bar(gc, x="Grade", y="Total", color="Grade", text="Total", color_discrete_map=cmap)
        fg.update_layout(template="plotly_white", height=178,
                         margin=dict(l=4,r=4,t=8,b=4), showlegend=False,
                         xaxis_title=None, yaxis_title=None,
                         font={"family":"Segoe UI, system-ui","size":10})
        fg.update_traces(textposition="outside", marker=dict(line=dict(width=0)))
        st.plotly_chart(fg, use_container_width=True, config={"displayModeBar":False})
with br:
    st.markdown("### Recent measurements")
    cols = ["received_at","temp_c","moisture_pct","turbidity_ntu","color_bright","iqk","grade","route"]
    avail = [c for c in cols if c in df.columns]
    hist = df[avail].tail(6).copy()
    if "received_at" in hist.columns:
        hist["received_at"] = hist["received_at"].dt.strftime("%H:%M:%S")
    st.dataframe(hist.iloc[::-1], use_container_width=True, hide_index=True, height=182)

# 9. REMOTE CONTROL (MQTT downlink) — butuh firmware onMqttCmd
st.divider()
st.markdown("### Remote control")
st.caption("Kirim perintah ke ESP32 via topic `jelantah/scanner/cmd`. Override pompa hanya aktif di mode manual (safety interlock).")

@st.cache_resource
def get_publisher():
    import paho.mqtt.client as mqtt
    c = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                    client_id="jelantah-ui-pub", protocol=mqtt.MQTTv311)
    c.connect(MQTT_HOST, MQTT_PORT); c.loop_start()
    return c

cc1, cc2 = st.columns([1, 1])
with cc1:
    st.markdown("**Pump override**")
    b1, b2, b3 = st.columns(3)
    if b1.button("ON"):   get_publisher().publish("jelantah/scanner/cmd", '{"pump":"on"}')
    if b2.button("OFF"):  get_publisher().publish("jelantah/scanner/cmd", '{"pump":"off"}')
    if b3.button("AUTO"): get_publisher().publish("jelantah/scanner/cmd", '{"pump":"auto"}')
with cc2:
    st.markdown("**Ambang moisture Grade B (%)**")
    th = st.slider("thr", 0.05, 1.0, 0.21, 0.01, label_visibility="collapsed")
    if st.button("Kirim ambang"):
        get_publisher().publish("jelantah/scanner/cmd", f'{{"th_b_moist":{th}}}')

# 10. FOOTER
st.divider()
fl, fr = st.columns(2)
fl.caption("Jelantah Scanner · IoT monitoring")
fr.caption("Auto-refresh 5 s · tren 30 pembacaan terakhir")