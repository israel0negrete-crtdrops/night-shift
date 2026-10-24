#!/usr/bin/env python3
"""En el N100: todo el flujo experimental pasa por aquí (0.0.0.0:7701 -> 127.0.0.1:7700).

Es donde se simulan las fallas de red, sólo para este flujo; la red de los equipos
no se toca. Falla de prueba control/red-<equipo>.json:
  {"modo": "corte", "hasta": epoch}             cierra y rechaza las conexiones de ese equipo
  {"modo": "latencia", "ms": 4000, "hasta": e}  retiene cada línea esos milisegundos
"""
import json
import socket
import socketserver
import threading
import time

from comun import PUERTO_COLECTOR, PUERTO_INTERMEDIARIO, anotar, bandera

EQUIPOS = {"192.168.3.163": "pios", "127.0.0.1": "israel-MINI-N100C"}


class Paso(socketserver.StreamRequestHandler):
    def handle(self):
        equipo = EQUIPOS.get(self.client_address[0], self.client_address[0])
        falla = bandera(f"red-{equipo}")
        if falla and falla.get("modo") == "corte":
            return                                   # rechaza: el equipo ve la conexión cerrada
        destino = socket.create_connection(("127.0.0.1", PUERTO_COLECTOR), timeout=5)
        try:
            for linea in self.rfile:
                falla = bandera(f"red-{equipo}")
                if falla and falla.get("modo") == "corte":
                    return
                if falla and falla.get("modo") == "latencia":
                    time.sleep(falla.get("ms", 0) / 1000)
                destino.sendall(linea)
        finally:
            destino.close()


class Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    anotar("intermediario", {"evento": "arranque"})
    Servidor(("0.0.0.0", PUERTO_INTERMEDIARIO), Paso).serve_forever()
