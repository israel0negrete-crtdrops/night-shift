#!/usr/bin/env python3
"""Las fallas de prueba de una noche, a horas fijas, con su verdad aparte.

    python3 fallas.py plan.json          # corre las fallas de este equipo, en orden
    python3 fallas.py plan.json --ahora  # prueba: todas seguidas, sin esperar la hora

Cada falla es controlada, reversible y sólo toca el flujo experimental (latido,
vigilante, intermediario) o carga acotada del propio equipo. Nunca reinicia el
equipo, ni toca su red real ni servicios del sistema. Lo que pasó de verdad
(inicio, fin real, qué se hizo) queda en datos/verdad-*.jsonl, que el detector no lee.

Plan: [{"hora": "23:10", "equipo": "pios", "escenario": "silencio", "min": 5, ...}, ...]
Escenarios:
  interrupcion  mata el latido; el vigilante lo levanta a los 30 s
  pausa         mata el latido y no lo deja volver hasta "hasta" (queda sin resolver)
  silencio      el latido sigue vivo pero no envía, "min" minutos
  corte         (en el N100) el intermediario rechaza el flujo de "de", "min" minutos
  latencia      (en el N100) el intermediario retiene cada latido de "de" "ms" ms, "min" minutos
  cpu           "procesos" bucles ocupados, "min" minutos; se corta si pasa de "temp_max" °C
  memoria       reserva memoria hasta dejar "dejar_pct" % disponible, "min" minutos;
                nunca baja de 600 MB disponibles
"""
import json
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta

from comun import CONTROL, EQUIPO, anotar, leer_jsonl, DATOS, dia

NOMBRE = {"israel-MINI-N100C": "N100", "pios": "Raspberry Pi 5"}


def verdad(**d):
    anotar("verdad", {"equipo_real": NOMBRE.get(EQUIPO, EQUIPO), **d})


def pid_latido():
    r = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", "turno/exp/bin/latido.py"], capture_output=True, text=True)
    return [int(p) for p in r.stdout.split()]


def arranque_despues(t0, limite=180):
    """Hora en que el vigilante volvió a arrancar el latido después de t0."""
    fin = time.time() + limite
    while time.time() < fin:
        for v in leer_jsonl([DATOS / f"vigilante-{dia()}.jsonl", DATOS / f"vigilante-{dia(t0)}.jsonl"]):
            if v.get("evento") == "arranque" and v["t"] > t0:
                return v["t"]
        time.sleep(2)
    return None


def bandera(nombre, segundos, **extra):
    (CONTROL / f"{nombre}.json").write_text(json.dumps({"hasta": time.time() + segundos, **extra}))


def ocupado(hasta):
    while time.time() < hasta:
        pass


def temperatura():
    vals = []
    for i in range(12):
        try:
            vals.append(int(open(f"/sys/class/thermal/thermal_zone{i}/temp").read()) / 1000)
        except (OSError, ValueError):
            pass
    return max(vals) if vals else 0


def disponible_mb():
    for linea in open("/proc/meminfo"):
        if linea.startswith("MemAvailable:"):
            return int(linea.split()[1]) // 1024
    return 0


def total_mb():
    for linea in open("/proc/meminfo"):
        if linea.startswith("MemTotal:"):
            return int(linea.split()[1]) // 1024
    return 0


def correr(f):
    esc, minutos = f["escenario"], f.get("min", 0)
    t0 = time.time()
    if esc == "interrupcion":
        for p in pid_latido():
            os.kill(p, signal.SIGTERM)
        vuelta = arranque_despues(t0)
        verdad(escenario=esc, inicio=t0, fin=vuelta, esperado="servicio reiniciado",
               detalle="latido terminado con SIGTERM; el vigilante lo vuelve a arrancar a los 30 s")
    elif esc == "pausa":
        hasta = datetime.strptime(f["hasta"], "%H:%M").replace(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
        if hasta.timestamp() < t0:
            hasta += timedelta(days=1)
        bandera("pausa", hasta.timestamp() - t0)
        for p in pid_latido():
            os.kill(p, signal.SIGTERM)
        verdad(escenario=esc, inicio=t0, fin=hasta.timestamp(), esperado="sin latido (sin resolver)",
               detalle=f"latido terminado y retenido por el vigilante hasta las {f['hasta']}")
    elif esc == "silencio":
        bandera("silencio", minutos * 60)
        time.sleep(minutos * 60)
        verdad(escenario=esc, inicio=t0, fin=time.time(), esperado="el equipo no envió",
               detalle=f"latido vivo sin enviar {minutos} min")
    elif esc in ("corte", "latencia"):
        extra = {"modo": esc}
        if esc == "latencia":
            extra["ms"] = f["ms"]
        bandera(f"red-{f['de']}", minutos * 60, **extra)
        time.sleep(minutos * 60)
        verdad(escenario=esc, inicio=t0, fin=time.time(), afectado=NOMBRE.get(f["de"], f["de"]),
               esperado="latidos perdidos en el camino" if esc == "corte" else "latencia",
               detalle=f"intermediario: {esc} del flujo de {f['de']}" + (f", {f['ms']} ms" if esc == "latencia" else "") + f", {minutos} min")
    elif esc == "cpu":
        hasta = t0 + minutos * 60
        procs = [multiprocessing.Process(target=ocupado, args=(hasta,)) for _ in range(f.get("procesos", os.cpu_count()))]
        for p in procs:
            p.start()
        cortado = None
        while time.time() < hasta:
            if temperatura() > f.get("temp_max", 80):
                cortado = temperatura()
                break
            time.sleep(5)
        for p in procs:
            p.terminate()
        verdad(escenario=esc, inicio=t0, fin=time.time(), esperado="saturación de CPU",
               detalle=f"{len(procs)} procesos ocupados {minutos} min" + (f"; cortado a {cortado:.1f} °C" if cortado else ""))
    elif esc == "memoria":
        objetivo = max(600, int(total_mb() * f.get("dejar_pct", 15) / 100))
        bloques = []
        while disponible_mb() > objetivo + 120:
            bloque = bytearray(100 * 1024 * 1024)
            for i in range(0, len(bloque), 4096):   # tocar cada página para que de verdad ocupe RAM
                bloque[i] = 1
            bloques.append(bloque)
            if disponible_mb() < 600:
                break
        lleno = time.time()
        time.sleep(minutos * 60)
        reservado = len(bloques) * 100
        del bloques
        verdad(escenario=esc, inicio=t0, fin=time.time(), esperado="memoria baja",
               detalle=f"{reservado} MB reservados hasta dejar ~{objetivo} MB; lleno a los {lleno - t0:.0f} s")


def main():
    plan = [f for f in json.load(open(sys.argv[1])) if f["equipo"] == EQUIPO]
    ya = "--ahora" in sys.argv
    hoy = datetime.now()
    for f in plan:
        if not ya:
            h, m = map(int, f["hora"].split(":"))
            cuando = hoy.replace(hour=h, minute=m, second=0, microsecond=0)
            if cuando < hoy - timedelta(hours=3):
                cuando += timedelta(days=1)
            espera = cuando.timestamp() - time.time()
            if espera > 0:
                time.sleep(espera)
        anotar("fallas", {"evento": "inicio", **f})
        try:
            correr(f)
        except Exception as e:  # una falla que no se pudo provocar no tumba las demás
            anotar("fallas", {"evento": "error", "error": repr(e), **f})


if __name__ == "__main__":
    main()
