#!/usr/bin/env python3
"""Mantiene vivo el latido, como haría systemd con Restart=on-failure, pero sin sudo.

Si el latido muere, espera 30 s y lo vuelve a arrancar. Falla de prueba "pausa"
(control/pausa.json): mientras exista, no lo arranca (el servicio se queda caído).
Cada arranque, caída y espera queda en datos/vigilante-*.jsonl.
"""
import subprocess
import sys
import time
from pathlib import Path

from comun import anotar, bandera

ESPERA = 30
AQUI = Path(__file__).resolve().parent


def main() -> None:
    while True:
        if bandera("pausa"):
            anotar("vigilante", {"evento": "en_pausa"})
            while bandera("pausa"):
                time.sleep(5)
        proc = subprocess.Popen([sys.executable, str(AQUI / "latido.py")], cwd=AQUI)
        anotar("vigilante", {"evento": "arranque", "pid": proc.pid})
        codigo = proc.wait()
        anotar("vigilante", {"evento": "caida", "pid": proc.pid, "codigo": codigo})
        time.sleep(ESPERA)


if __name__ == "__main__":
    main()
