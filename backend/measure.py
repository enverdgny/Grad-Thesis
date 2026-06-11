"""Ölçüm çekirdeği — düğümler arası iperf3 (TCP/UDP) ve ping ölçümleri.

Tüm komutlar `docker exec` ile ilgili düğüm container'ı içinde çalıştırılır.
Hiçbir fonksiyon istisna fırlatmaz; hata durumunda ilgili alanlar None döner.
"""

import json
import re
import subprocess

from . import config


def _exec(node: str, cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Bir düğüm container'ı içinde komut çalıştırır."""
    return subprocess.run(
        ["docker", "exec", node, *cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def node_running(node: str) -> bool:
    """Container 'running' durumunda mı?"""
    try:
        r = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", node],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() == "true"
    except Exception:
        return False


def measure_tcp(src: str, dst_ip: str) -> dict:
    """TCP throughput (Mbit/s) ve retransmit sayısı."""
    try:
        r = _exec(src, ["iperf3", "-c", dst_ip, "-t", str(config.IPERF_DURATION), "-J"])
        data = json.loads(r.stdout)
        end = data["end"]
        return {
            "throughput_mbps": round(end["sum_received"]["bits_per_second"] / 1e6, 2),
            "retransmits": end["sum_sent"].get("retransmits", 0),
        }
    except Exception:
        return {"throughput_mbps": None, "retransmits": None}


def measure_udp(src: str, dst_ip: str) -> dict:
    """UDP testinden jitter (ms) ve paket kaybı (%)."""
    try:
        r = _exec(src, ["iperf3", "-c", dst_ip, "-u",
                        "-b", config.UDP_BANDWIDTH,
                        "-t", str(config.IPERF_DURATION), "-J"])
        data = json.loads(r.stdout)
        summary = data["end"]["sum"]
        return {
            "jitter_ms": round(summary["jitter_ms"], 3),
            "loss_pct": round(summary["lost_percent"], 2),
        }
    except Exception:
        return {"jitter_ms": None, "loss_pct": None}


_RTT_RE = re.compile(r"=\s*[\d.]+/([\d.]+)/")  # min/AVG/max/mdev


def measure_ping(src: str, dst_ip: str) -> dict:
    """Ping ile ortalama gecikme (ms)."""
    try:
        r = _exec(src, ["ping", "-c", str(config.PING_COUNT), "-i", "0.2", dst_ip])
        m = _RTT_RE.search(r.stdout)
        return {"latency_ms": round(float(m.group(1)), 3) if m else None}
    except Exception:
        return {"latency_ms": None}


def measure_link(src: str, dst: str) -> dict:
    """Tek bir bağlantı için tüm metrikleri ölçer ve birleştirir."""
    dst_ip = config.NODES[dst]["ip"]
    record = {
        "src": src, "src_display": config.NODES[src]["display"],
        "dst": dst, "dst_display": config.NODES[dst]["display"],
    }
    record.update(measure_ping(src, dst_ip))
    record.update(measure_tcp(src, dst_ip))
    record.update(measure_udp(src, dst_ip))
    # Bağlantı, en az bir metrik döndüyse "up" sayılır
    record["up"] = record.get("latency_ms") is not None or record.get("throughput_mbps") is not None
    return record
