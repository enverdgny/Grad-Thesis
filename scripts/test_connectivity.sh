#!/bin/bash
# ============================================================================
#  1. Adım Doğrulama Betiği
#  Düğümlerin ayakta olduğunu, birbirini gördüğünü ve iperf3 ölçümünün
#  çalıştığını uçtan uca test eder.
# ============================================================================
set -e

NODES=("karargah" "iha1" "iha2" "tank1")

echo "=========================================="
echo " 1) Çalışan düğümler"
echo "=========================================="
docker compose ps

echo
echo "=========================================="
echo " 2) Ağ bağlantısı (ping: Karargah -> diğerleri)"
echo "=========================================="
for target in iha1 iha2 tank1; do
  echo "--- Karargah -> ${target} ---"
  docker exec karargah ping -c 3 "${target}"
done

echo
echo "=========================================="
echo " 3) iperf3 TCP throughput testi (Karargah -> İHA-1)"
echo "=========================================="
docker exec karargah iperf3 -c iha1 -t 3

echo
echo "=========================================="
echo " 4) iperf3 UDP testi — jitter & paket kaybı (Karargah -> Tank-1)"
echo "=========================================="
docker exec karargah iperf3 -c tank1 -u -b 10M -t 3

echo
echo "✅ 1. Adım doğrulaması tamamlandı."
