"""Lo que comparten las piezas del turno de noche: rutas, hora y registro en JSONL.

Todo vive en ~/turno/exp de cada equipo y corre como el usuario del laboratorio,
sin sudo. Nada de esto toca servicios del sistema ni la red de los equipos.
"""
import json
import os
import socket
import time
from pathlib import Path

BASE = Path.home() / "turno" / "exp"
DATOS = BASE / "datos"          # mediciones locales de este equipo
CONTROL = BASE / "control"      # banderas de las fallas de prueba
INFORMES = BASE / "informes"    # JSON y Markdown de cada mañana (en el N100)
for d in (DATOS, CONTROL, INFORMES):
    d.mkdir(parents=True, exist_ok=True)

EQUIPO = socket.gethostname()
N100 = "192.168.3.135"
PUERTO_COLECTOR = 7700          # sólo en 127.0.0.1 del N100
PUERTO_INTERMEDIARIO = 7701     # por aquí entra el flujo experimental
PUERTO_INFORMES = 7702          # lectura de los informes, para la Pi
INTERVALO = 10                  # segundos entre latidos


def ahora() -> float:
    return time.time()


def dia(t: float | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t or ahora()))


def anotar(nombre: str, registro: dict) -> None:
    """Agrega una línea JSON a datos/<nombre>-<día>.jsonl."""
    registro.setdefault("t", ahora())
    ruta = DATOS / f"{nombre}-{dia(registro['t'])}.jsonl"
    with open(ruta, "a") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def leer_jsonl(rutas) -> list[dict]:
    filas = []
    for ruta in rutas:
        try:
            with open(ruta) as f:
                for linea in f:
                    linea = linea.strip()
                    if linea:
                        try:
                            filas.append(json.loads(linea))
                        except json.JSONDecodeError:
                            pass
        except FileNotFoundError:
            pass
    return filas


def bandera(nombre: str) -> dict | None:
    """Una falla de prueba activa: control/<nombre>.json con {"hasta": epoch, ...}."""
    ruta = CONTROL / f"{nombre}.json"
    try:
        d = json.loads(ruta.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if d.get("hasta", 0) < ahora():
        return None
    return d
