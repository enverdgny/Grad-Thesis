# Sanal Taktik Saha Ağ Simülatörü ve Performans İzleme Paneli

Bitirme tezi projesi — Docker ile izole sanal düğümler arasında ağ performansı
(bant genişliği, gecikme, jitter, paket kaybı) ölçen ve canlı bir panelde
görselleştiren modüler bir sistem.

## Mimari

| Düğüm | Container | IP | Rol |
|-------|-----------|----|----|
| Karargah | `karargah` | 172.30.0.10 | Komuta merkezi |
| İHA-1 | `iha1` | 172.30.0.11 | İnsansız hava aracı |
| İHA-2 | `iha2` | 172.30.0.12 | İnsansız hava aracı |
| Tank-1 | `tank1` | 172.30.0.13 | Kara birimi |

Tüm düğümler `tactical_net` (172.30.0.0/24) özel bridge ağında, sabit IP ile
çalışır. Her düğüm bir `iperf3` sunucusu (`:5201`) barındırır; ölçümler bir
düğümden diğerine istemci bağlantısıyla yapılır.

## Yol Haritası

- [x] **1. Adım — Docker topolojisi + iperf3 altyapısı** *(tamamlandı)*
- [x] **2. Adım — Python ölçüm motoru** (iperf3 TCP/UDP + ping, JSON loglama) *(tamamlandı)*
- [x] **3. Adım — Streamlit canlı izleme paneli** *(tamamlandı)*
- [x] **4. Adım — `tc/netem` ile gerçekçi saha koşulları** (gecikme/jitter/kayıp/bant) *(2. Adım'a entegre edildi)*

## Bileşenler

| Dosya | Görev |
|-------|-------|
| `docker-compose.yml`, `docker/` | 4 düğümlü izole ağ topolojisi (iperf3 sunuculu) |
| `backend/config.py` | Düğümler, bağlantılar, netem profilleri, parametreler |
| `backend/measure.py` | iperf3 TCP/UDP + ping ölçüm çekirdeği |
| `backend/netem.py` | tc/netem ile yapay saha koşulları |
| `backend/engine.py` | Periyodik ölçüm döngüsü + JSONL/JSON loglama |
| `ui/dashboard.py` | Streamlit canlı izleme paneli |

## Kurulum

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Kullanım

```bash
# En kolay yol: Docker düğümleri + panel tek komutla
./run.sh                      # -> http://localhost:8501
# (Ölçümü panelin içindeki "▶ Başlat" düğmesiyle aç/kapat.)

# --- veya bileşenleri ayrı ayrı ---
docker compose up -d --build              # düğümleri başlat
./scripts/test_connectivity.sh            # uçtan uca doğrulama
.venv/bin/python -m backend.engine        # netem uygulayıp sürekli ölç
.venv/bin/python -m backend.engine --once # tek tur ölç
.venv/bin/python -m backend.netem clear   # netem kurallarını temizle
.venv/bin/streamlit run ui/dashboard.py   # paneli aç

docker compose down                       # her şeyi durdur
```

## Not — Gerçekçi koşullar (netem)
Düğümler aynı host üzerinde olduğundan ham throughput gerçekçi değildir
(~100+ Gbit/s). `backend/netem.py`, her düğümün egress arayüzüne `tc/netem`
ile bant sınırı + gecikme + jitter + paket kaybı uygular; böylece ölçülen
metrikler gerçek bir taktik radyo bağlantısına benzer. Profiller
`backend/config.py` içindeki `NETEM_PROFILES` ile ayarlanır. Bu yüzden imajda
`iproute2` ve container'larda `NET_ADMIN` yetkisi tanımlıdır.
