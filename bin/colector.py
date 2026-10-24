#!/usr/bin/env python3
"""En el N100: recibe los latidos (sólo desde el intermediario) y sirve los informes.

- 127.0.0.1:7700: líneas JSON; agrega la hora de llegada y las guarda en
  datos/recibidos-*.jsonl.
- 0.0.0.0:7702: HTTP de sólo lectura de informes/, para que la Pi baje el JSON
  de la mañana y redacte su versión.
"""
import functools
import http.server
import json
import socketserver
import threading

from comun import INFORMES, PUERTO_COLECTOR, PUERTO_INFORMES, ahora, anotar


class Latidos(socketserver.StreamRequestHandler):
    def handle(self):
        for linea in self.rfile:
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                continue
            anotar("recibidos", {**d, "t": ahora(), "recibido": ahora()})


class Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def informes() -> None:
    manejador = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(INFORMES))
    manejador.log_message = lambda *a, **k: None
    http.server.ThreadingHTTPServer(("0.0.0.0", PUERTO_INFORMES), manejador).serve_forever()


if __name__ == "__main__":
    threading.Thread(target=informes, daemon=True).start()
    Servidor(("127.0.0.1", PUERTO_COLECTOR), Latidos).serve_forever()
