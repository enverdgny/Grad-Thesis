#!/bin/bash
# Tüm sistemi başlatır: Docker düğümleri + Streamlit panel.
# Ölçüm motoru panelin içindeki "▶ Başlat" düğmesiyle kontrol edilir.
set -e
cd "$(dirname "$0")"

echo "1) Docker düğümleri ayağa kaldırılıyor..."
docker compose up -d --build

echo "2) Panel başlatılıyor -> http://localhost:8501"
exec .venv/bin/streamlit run ui/dashboard.py
