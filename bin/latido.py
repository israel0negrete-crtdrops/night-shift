#!/usr/bin/env python3
"""El servicio experimental: cada 10 s manda un latido al N100 y lo guarda en local.

El latido lleva número de secuencia, hora de envío, hora de arranque del proceso,
carga, memoria disponible y temperatura. Si no puede enviar, lo anota en local
(datos/latido-*.jsonl) con el motivo, para que la evidencia no dependa de la red.

Falla de prueba "silencio" (control/silencio.json): el proceso sigue vivo pero no
envía; lo anota en local como no enviado.
"""
import json
import os
import socket
import time

from comun import EQUIPO, INTERVALO, N100, PUERTO_INTERMEDIARIO, ahora, anotar, bandera

ARRANQUE = ahora()
DESTINO = ("127.0.0.1" if EQUIPO.startswith("israel-MINI") else N100, PUERTO_INTERMEDIARIO)


def temperatura() -> float | None:
    mayor = None
    for i in range(12):
        try:
            with open(f"/sys/class/thermal/thermal_zone{i}/temp") as f:
                v = int(f.read()) / 1000
            mayor = v if mayor is None else max(mayor, v)
        except (FileNotFoundError, ValueError, OSError):
            continue
    return mayor


def memoria() -> tuple[int, int]:
    total = disp = 0
    with open("/proc/meminfo") as f:
        for linea in f:
            if linea.startswith("MemTotal:"):
                total = int(linea.split()[1]) // 1024
            elif linea.startswith("MemAvailable:"):
                disp = int(linea.split()[1]) // 1024
    return total, disp


def main() -> None:
    conexion = None
    seq = 0
    no_enviados = 0
    while True:
        inicio = time.monotonic()
        seq += 1
        total, disp = memoria()
        latido = {"equipo": EQUIPO, "seq": seq, "enviado": ahora(), "arranque": ARRANQUE,
                  "carga1": os.getloadavg()[0], "cpus": os.cpu_count(), "mem_total_mb": total,
                  "mem_disp_mb": disp, "temp_c": temperatura(), "no_enviados": no_enviados}
        estado, motivo = "enviado", None
        if bandera("silencio"):
            estado, motivo = "no_enviado", "silencio"
        else:
            try:
                if conexion is None:
                    conexion = socket.create_connection(DESTINO, timeout=5)
                conexion.sendall((json.dumps(latido) + "\n").encode())
            except OSError as e:
                estado, motivo = "no_enviado", type(e).__name__
                try:
                    conexion and conexion.close()
                except OSError:
                    pass
                conexion = None
        if estado != "enviado":
            no_enviados += 1
        anotar("latido", {**latido, "t": latido["enviado"], "estado": estado, "motivo": motivo})
        time.sleep(max(0.5, INTERVALO - (time.monotonic() - inicio)))


if __name__ == "__main__":
    main()
