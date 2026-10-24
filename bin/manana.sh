#!/usr/bin/env bash
# La mañana (crontab del usuario del laboratorio).
#   N100, 6:30: el detector escribe el JSON y Gemma redacta el Markdown.
#   Pi 5, 6:40: baja ese JSON del N100 y Gemma redacta su propia versión.
cd "$(dirname "$0")"
export OLLAMA_HOST=127.0.0.1:11434
INFORMES="$HOME/turno/exp/informes"
nombre="noche-$(date +%F)"
if [ "$(hostname)" = "israel-MINI-N100C" ]; then
  python3 detector.py && python3 redactor.py "$INFORMES/$nombre.json"
else
  curl -fsS -o "$INFORMES/$nombre.json" "http://192.168.3.135:7702/$nombre.json" \
    && python3 redactor.py "$INFORMES/$nombre.json"
fi >>"$HOME/turno/exp/datos/manana.log" 2>&1
