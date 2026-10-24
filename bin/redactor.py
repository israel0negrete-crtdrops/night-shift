#!/usr/bin/env python3
"""Gemma redacta el reporte de las 7:00 a partir del JSON del detector. Sólo redacta.

    python3 redactor.py informes/noche-2026-10-20.json

Escribe junto al JSON <nombre>.<equipo>.md y <nombre>.<equipo>.medicion.json
(tiempos y tokens de Ollama, memoria y temperatura del equipo antes y después).
Modelo fijo, temperatura 0 y semilla 42.
"""
import json
import socket
import sys
import time
import urllib.request
from pathlib import Path

MODELO = "gemma3:4b"
OLLAMA = "http://127.0.0.1:11434/api/generate"
OPCIONES = {"temperature": 0, "seed": 42, "num_ctx": 8192}

INSTRUCCIONES = """Eres el turno de noche de un laboratorio con dos equipos. Escribe en español el
reporte de las 7:00 a partir del JSON de abajo, que produjo un detector con reglas fijas.

Reglas estrictas:
- Usa sólo horas, cifras y hechos que estén en el JSON. No agregues ninguno.
- No inventes causas. Para cada incidente separa: "Hechos observados" (lo que dice la
  evidencia), "Posibles explicaciones" (marcadas como no confirmadas) y "Causa confirmada"
  (escribe "no confirmada" salvo que la evidencia la confirme).
- Si no hubo incidentes, dilo en una línea y no inventes problemas.
- No califiques temperatura, memoria ni carga (por ejemplo "elevada"): el detector ya decide eso; sólo
  menciónalas si hay un incidente de ese tipo.
- Breve: es para leerse en un minuto.

Formato (Markdown):
# Turno de noche: <fecha de "hasta">
**Salud general:** <buena|regular|mala>. <Una oración con el porcentaje de latidos recibidos de cada equipo.>
## Incidentes
Para cada uno: equipo, tipo, inicio, fin, duración, si se recuperó solo, cuándo se detectó; luego
Hechos observados / Posibles explicaciones / Causa confirmada.
## Sin resolver
## Recomendaciones
Acciones concretas para verificar, sin afirmar causas.
## Comparación con la noche anterior
Sólo si el JSON trae "comparacion"; si no, escribe "Sin noche anterior para comparar."

JSON:
"""


def estado_equipo():
    disp = None
    with open("/proc/meminfo") as f:
        for linea in f:
            if linea.startswith("MemAvailable:"):
                disp = int(linea.split()[1]) // 1024
    temps = []
    for i in range(12):
        try:
            temps.append(int(open(f"/sys/class/thermal/thermal_zone{i}/temp").read()) / 1000)
        except (OSError, ValueError):
            pass
    return {"mem_disp_mb": disp, "temp_max_c": max(temps) if temps else None}


def main():
    entrada = Path(sys.argv[1])
    datos = json.loads(entrada.read_text())
    equipo = socket.gethostname()
    antes = estado_equipo()
    cuerpo = json.dumps({"model": MODELO, "prompt": INSTRUCCIONES + json.dumps(datos, ensure_ascii=False, indent=1),
                         "stream": False, "options": OPCIONES}).encode()
    t0 = time.time()
    pet = urllib.request.Request(OLLAMA, data=cuerpo, headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(pet, timeout=3600))
    s = 1e9
    medicion = {
        "equipo": equipo, "modelo": MODELO, "opciones": OPCIONES, "inicio": t0, "pared_s": round(time.time() - t0, 1),
        "total_s": round(r["total_duration"] / s, 1), "carga_s": round(r["load_duration"] / s, 1),
        "tokens_entrada": r.get("prompt_eval_count"), "tokens_salida": r.get("eval_count"),
        "entrada_tok_s": round(r["prompt_eval_count"] / (r["prompt_eval_duration"] / s), 1),
        "salida_tok_s": round(r["eval_count"] / (r["eval_duration"] / s), 1),
        "antes": antes, "despues": estado_equipo(),
    }
    base = entrada.with_suffix("")
    Path(f"{base}.{equipo}.md").write_text(r["response"].strip() + "\n")
    Path(f"{base}.{equipo}.medicion.json").write_text(json.dumps(medicion, ensure_ascii=False, indent=2))
    print(f"{base}.{equipo}.md", medicion["total_s"], "s")


if __name__ == "__main__":
    main()
