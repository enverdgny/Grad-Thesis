"""Ölçüm motoru — bağlantıları periyodik ölçer, JSON olarak loglar.

Çalıştırma:
    python -m backend.engine            # netem uygulayıp sürekli ölçer
    python -m backend.engine --once     # tek tur ölçüm yapıp çıkar
    python -m backend.engine --no-netem # netem uygulamadan ölçer
"""

import argparse
import datetime
import json
import os
import time

from . import config, measure, netem

# Proje kökü (backend/ dizininin bir üstü)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _path(rel: str) -> str:
    return os.path.join(ROOT, rel)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_cycle() -> list[dict]:
    """Tüm bağlantıları sırayla ölçer, kayıtları döndürür ve diske yazar."""
    ts = _now()
    records = []

    for src, dst in config.LINKS:
        rec = measure.measure_link(src, dst)
        rec["ts"] = ts
        records.append(rec)
        flag = "✓" if rec["up"] else "✗"
        print(f"  {flag} {rec['src_display']:>8} → {rec['dst_display']:<8} "
              f"| {str(rec.get('throughput_mbps')):>8} Mbps "
              f"| {str(rec.get('latency_ms')):>7} ms "
              f"| jitter {str(rec.get('jitter_ms')):>6} ms "
              f"| kayıp {str(rec.get('loss_pct')):>5}%")

    # Zaman serisine ekle (append-only JSONL)
    with open(_path(config.METRICS_FILE), "a") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Anlık düğüm durumu anlık görüntüsü
    status = {
        "updated": ts,
        "nodes": {
            node: {
                "display": info["display"],
                "ip": info["ip"],
                "running": measure.node_running(node),
            }
            for node, info in config.NODES.items()
        },
    }
    with open(_path(config.STATUS_FILE), "w") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Taktik saha ölçüm motoru")
    parser.add_argument("--once", action="store_true", help="Tek tur ölç ve çık")
    parser.add_argument("--no-netem", action="store_true", help="netem uygulama")
    args = parser.parse_args()

    os.makedirs(_path("logs"), exist_ok=True)

    if not args.no_netem:
        netem.apply_all()
        print()

    if args.once:
        print(f"[{_now()}] Tek tur ölçüm:")
        run_cycle()
        return

    print(f"Sürekli ölçüm başladı (her ~{config.INTERVAL_SEC}s + ölçüm süresi). "
          f"Durdurmak için Ctrl+C.\n")
    try:
        while True:
            print(f"[{_now()}]")
            run_cycle()
            time.sleep(config.INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\nÖlçüm durduruldu.")


if __name__ == "__main__":
    main()
