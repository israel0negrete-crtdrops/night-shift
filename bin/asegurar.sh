#!/usr/bin/env bash
# Cada 5 minutos (crontab del usuario del laboratorio): arranca lo que no esté
# corriendo. No reinicia nada que ya corra, ni toca servicios del sistema.
cd "$(dirname "$0")"
export OLLAMA_MODELS="$HOME/turno/modelos" OLLAMA_HOST=127.0.0.1:11434
mkdir -p "$HOME/turno/exp/datos"
arrancar() {  # nombre, comando...
  local nombre=$1; shift
  pgrep -u "$(id -u)" -f "$nombre" >/dev/null || (setsid nohup "$@" >>"$HOME/turno/exp/datos/procesos.log" 2>&1 </dev/null &)
}
arrancar "ollama serve" "$HOME/turno/ollama/bin/ollama" serve
if [ "$(hostname)" = "israel-MINI-N100C" ]; then
  arrancar "colector.py" python3 colector.py
  sleep 1
  arrancar "intermediario.py" python3 intermediario.py
fi
arrancar "vigilante.py" python3 vigilante.py
