"""Sistem yapılandırması — düğümler, ölçülecek bağlantılar ve saha koşulları."""

# Düğüm tanımları (container adı -> görünen ad + IP)
NODES = {
    "karargah": {"display": "Karargah", "ip": "172.30.0.10"},
    "iha1":     {"display": "İHA-1",    "ip": "172.30.0.11"},
    "iha2":     {"display": "İHA-2",    "ip": "172.30.0.12"},
    "tank1":    {"display": "Tank-1",   "ip": "172.30.0.13"},
}

# Ölçülecek yönlü bağlantılar: (kaynak, hedef)
LINKS = [
    ("karargah", "iha1"),
    ("karargah", "iha2"),
    ("karargah", "tank1"),
    ("iha1",     "iha2"),
    ("tank1",    "iha1"),
]

# ---------------------------------------------------------------------------
# netem (tc) profilleri — her düğümün EGRESS trafiğine uygulanır.
# Gerçek taktik saha radyolarını taklit eder: sınırlı bant, gecikme, kayıp.
#   delay_ms  : ortalama tek yön gecikme
#   jitter_ms : gecikmedeki rastgele sapma
#   loss_pct  : paket kaybı yüzdesi
#   rate      : bağlantı kapasitesi (radyo bant genişliği benzetimi)
# ---------------------------------------------------------------------------
NETEM_PROFILES = {
    "karargah": {"delay_ms": 5,  "jitter_ms": 1,  "loss_pct": 0.1, "rate": "100mbit"},
    "iha1":     {"delay_ms": 25, "jitter_ms": 5,  "loss_pct": 1.0, "rate": "50mbit"},
    "iha2":     {"delay_ms": 40, "jitter_ms": 10, "loss_pct": 2.0, "rate": "20mbit"},
    "tank1":    {"delay_ms": 15, "jitter_ms": 3,  "loss_pct": 0.5, "rate": "30mbit"},
}

# Ölçüm parametreleri
INTERVAL_SEC   = 3       # her tam tur arasındaki bekleme
IPERF_DURATION = 2       # her iperf3 testinin süresi (sn)
UDP_BANDWIDTH  = "20M"   # UDP testi hedef hızı (jitter/kayıp ölçümü için)
PING_COUNT     = 4       # gecikme ölçümü için ping paketi sayısı

# Çıktı dosyaları (proje köküne göre)
METRICS_FILE = "logs/metrics.jsonl"   # append-only zaman serisi
STATUS_FILE  = "logs/status.json"     # anlık düğüm durumu anlık görüntüsü
