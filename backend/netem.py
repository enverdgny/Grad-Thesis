"""tc/netem ile yapay saha koşulları — düğüm egress'ine gecikme/jitter/kayıp/hız.

Aynı host üzerindeki container'lar gerçekçi olmayan throughput (~100+ Gbit/s)
ürettiğinden, her düğümün eth0 arayüzüne bir netem profili uygulanır. Böylece
ölçülen metrikler gerçek bir taktik radyo bağlantısına benzer.
"""

import subprocess

from . import config


def _tc(node: str, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", node, "tc", *args],
        capture_output=True, text=True, timeout=15,
    )


def apply_profile(node: str, profile: dict) -> str:
    """Bir düğüme netem profilini uygular (önceki kuralı temizleyerek)."""
    # Var olan kök qdisc'i temizle (yoksa hatayı yut)
    _tc(node, ["qdisc", "del", "dev", "eth0", "root"])

    netem = [
        "qdisc", "add", "dev", "eth0", "root", "netem",
        "delay", f"{profile['delay_ms']}ms", f"{profile['jitter_ms']}ms",
        "loss", f"{profile['loss_pct']}%",
        "rate", profile["rate"],
    ]
    r = _tc(node, netem)
    if r.returncode != 0:
        return f"HATA: {r.stderr.strip()}"
    return (f"{profile['rate']}, gecikme {profile['delay_ms']}±{profile['jitter_ms']}ms, "
            f"kayıp {profile['loss_pct']}%")


def clear_profile(node: str) -> None:
    """Düğümdeki netem kuralını kaldırır."""
    _tc(node, ["qdisc", "del", "dev", "eth0", "root"])


def apply_all() -> None:
    print("netem profilleri uygulanıyor (taktik saha koşulları)...")
    for node, profile in config.NETEM_PROFILES.items():
        result = apply_profile(node, profile)
        print(f"  [{config.NODES[node]['display']:<9}] {result}")


def clear_all() -> None:
    print("netem profilleri temizleniyor...")
    for node in config.NETEM_PROFILES:
        clear_profile(node)
        print(f"  [{config.NODES[node]['display']:<9}] temizlendi")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_all()
    else:
        apply_all()
