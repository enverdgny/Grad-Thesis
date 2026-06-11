"""Sanal Taktik Saha — Canlı Performans İzleme Paneli (Streamlit).

Çalıştırma (proje kökünden):
    .venv/bin/streamlit run ui/dashboard.py

Panel, ölçüm motorunu kenar çubuğundan başlatıp durdurabilir; metrikleri
logs/metrics.jsonl dosyasından canlı okuyup akan grafiklerle gösterir.
"""

import json
import os
import subprocess
import sys

import pandas as pd
import streamlit as st

# Proje kökü ve backend'e erişim için path ayarı
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend import config  # noqa: E402

METRICS_PATH = os.path.join(ROOT, config.METRICS_FILE)
STATUS_PATH = os.path.join(ROOT, config.STATUS_FILE)

st.set_page_config(page_title="Taktik Saha Ağ İzleme", page_icon="📡", layout="wide")


# --------------------------------------------------------------------------
# Motor (ölçüm süreci) kontrolü
# --------------------------------------------------------------------------
def engine_running() -> bool:
    p = st.session_state.get("engine")
    return p is not None and p.poll() is None


def start_engine(use_netem: bool) -> None:
    if engine_running():
        return
    cmd = [sys.executable, "-m", "backend.engine"]
    if not use_netem:
        cmd.append("--no-netem")
    log = open(os.path.join(ROOT, "logs", "engine.out"), "a")
    st.session_state.engine = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=log)


def stop_engine() -> None:
    p = st.session_state.get("engine")
    if p is not None and p.poll() is None:
        p.terminate()
    st.session_state.engine = None


# --------------------------------------------------------------------------
# Veri yükleme
# --------------------------------------------------------------------------
def load_metrics() -> pd.DataFrame:
    if not os.path.exists(METRICS_PATH):
        return pd.DataFrame()
    rows = []
    with open(METRICS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"])
    df["link"] = df["src_display"] + " → " + df["dst_display"]
    return df


def load_status() -> dict:
    if not os.path.exists(STATUS_PATH):
        return {}
    try:
        with open(STATUS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# --------------------------------------------------------------------------
# Kenar çubuğu — kontroller
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Kontrol")
    use_netem = st.checkbox("Yapay saha koşulları (netem)", value=True,
                            help="tc/netem ile gerçekçi gecikme, jitter, kayıp ve bant sınırı uygular.")

    c1, c2 = st.columns(2)
    if c1.button("▶ Başlat", use_container_width=True, type="primary"):
        start_engine(use_netem)
    if c2.button("■ Durdur", use_container_width=True):
        stop_engine()

    if engine_running():
        st.success("Ölçüm motoru ÇALIŞIYOR")
    else:
        st.warning("Ölçüm motoru durdu")

    st.divider()
    window = st.slider("Grafik penceresi (son N ölçüm/bağlantı)", 10, 200, 60, step=10)
    refresh = st.slider("Yenileme aralığı (sn)", 1, 10, 3)


# --------------------------------------------------------------------------
# Ana içerik — canlı yenilenen fragment
# --------------------------------------------------------------------------
st.title("📡 Sanal Taktik Saha — Ağ Performans İzleme")


@st.fragment(run_every=f"{refresh}s")
def live_view():
    status = load_status()
    df = load_metrics()

    # ---- Düğüm durum kartları ----
    st.subheader("Düğüm Durumları")
    nodes = status.get("nodes", {})
    cols = st.columns(len(config.NODES))
    for col, (node, info) in zip(cols, config.NODES.items()):
        running = nodes.get(node, {}).get("running", False)
        badge = "🟢 AKTİF" if running else "🔴 PASİF"
        col.metric(info["display"], badge, info["ip"])

    if df.empty:
        st.info("Henüz veri yok. Soldaki **▶ Başlat** ile ölçüm motorunu çalıştırın.")
        return

    # ---- Bağlantı seçimi ----
    links = sorted(df["link"].unique())
    selected = st.multiselect("Görüntülenecek bağlantılar", links, default=links)
    view = df[df["link"].isin(selected)]
    if view.empty:
        st.info("Bir bağlantı seçin.")
        return

    # Son N ölçümle sınırla (bağlantı başına)
    view = view.groupby("link", group_keys=False).tail(window)

    # ---- Özet metrik kartları (en güncel değerler, tüm seçili bağlantı ort.) ----
    latest = view.sort_values("ts").groupby("link").tail(1)
    st.subheader("Anlık Özet (seçili bağlantılar ortalaması)")
    m = st.columns(4)
    m[0].metric("Ort. Throughput", f"{latest['throughput_mbps'].mean():.1f} Mbps")
    m[1].metric("Ort. Gecikme", f"{latest['latency_ms'].mean():.1f} ms")
    m[2].metric("Ort. Jitter", f"{latest['jitter_ms'].mean():.2f} ms")
    m[3].metric("Ort. Paket Kaybı", f"{latest['loss_pct'].mean():.2f} %")

    # ---- Canlı akan grafikler ----
    st.subheader("Canlı Performans Grafikleri")

    def chart(metric: str, title: str):
        pivot = view.pivot_table(index="ts", columns="link", values=metric)
        st.caption(title)
        st.line_chart(pivot, height=240)

    g1, g2 = st.columns(2)
    with g1:
        chart("throughput_mbps", "Bant Genişliği / Throughput (Mbps)")
        chart("jitter_ms", "Jitter (ms)")
    with g2:
        chart("latency_ms", "Gecikme / Latency (ms)")
        chart("loss_pct", "Paket Kaybı (%)")

    st.caption(f"Son güncelleme: {status.get('updated', '—')} · Toplam kayıt: {len(df)}")


live_view()
