#!/bin/bash
# Her düğüm bir iperf3 SUNUCUSU çalıştırır. Böylece herhangi bir düğüm,
# bir diğerine iperf3 İSTEMCİSİ olarak bağlanıp ölçüm yapabilir.
set -e

NODE_NAME="${NODE_NAME:-unknown}"
echo "[${NODE_NAME}] Dugum baslatiliyor -> iperf3 sunucusu :5201 dinlemede"

# -s : server modu | -p : port | --forceflush: log akisini aninda bosalt
# Birden fazla es-zamanli teste izin vermek icin -D ile daemonlastirmiyoruz;
# tek instance on planda calisir ve testler orchestrator tarafindan siralanir.
exec iperf3 -s -p 5201 --forceflush
