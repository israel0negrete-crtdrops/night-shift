#!/usr/bin/env python3
"""En el N100, a las 6:30: decide con reglas fijas qué pasó en la noche. Sin modelo.

    python3 detector.py                      # la noche que acaba de terminar (22:00 a 06:30)
    python3 detector.py --desde 1792000000 --hasta 1792030000 --nombre prueba

Lee los latidos recibidos (datos/recibidos-*.jsonl) y los registros locales del
N100, y escribe informes/noche-<día>.json con incidentes, evidencia, salud y la
comparación con la noche anterior. Las reglas:

- sin latido: más de 30 s (3 intervalos) sin recibir nada de un equipo;
  se clasifica por lo que trae el siguiente latido (proceso nuevo, latidos que el
  equipo anotó como no enviados, o enviados que no llegaron);
- latencia: llegada menos envío, 2 s por encima de la mediana de la noche, en 3
  latidos seguidos;
- CPU: carga de 1 minuto por encima del 75 % de los núcleos en 3 latidos seguidos;
- memoria: menos del 20 % disponible en 3 latidos seguidos;
- temperatura: más de 80 °C en 3 latidos seguidos.
"""
import argparse
import json
import statistics
import time
from datetime import datetime, timedelta

from comun import DATOS, INFORMES, INTERVALO, dia, leer_jsonl

HUECO = 3 * INTERVALO
EQUIPOS = ["israel-MINI-N100C", "pios"]
NOMBRE = {"israel-MINI-N100C": "N100", "pios": "Raspberry Pi 5"}


def hora(t):
    return None if t is None else time.strftime("%H:%M:%S", time.localtime(t))


def ventana_de_anoche():
    hoy = datetime.now().replace(hour=6, minute=30, second=0, microsecond=0)
    return (hoy - timedelta(hours=8, minutes=30)).timestamp(), hoy.timestamp()


def archivos(nombre, desde, hasta):
    dias = {dia(desde), dia(hasta)}
    return [DATOS / f"{nombre}-{d}.jsonl" for d in sorted(dias)]


def rachas(filas, condicion, minimo=3):
    """Tramos de al menos `minimo` latidos seguidos que cumplen la condición."""
    tramos, actual = [], []
    for f in filas:
        if condicion(f):
            actual.append(f)
        else:
            if len(actual) >= minimo:
                tramos.append(actual)
            actual = []
    if len(actual) >= minimo:
        tramos.append(actual)
    return tramos


def incidentes_de(equipo, filas, desde, hasta, vigilante):
    salida = []

    def nuevo(tipo, inicio, fin, detectado, evidencia, **extra):
        abierto = fin is None
        salida.append({"equipo": NOMBRE.get(equipo, equipo), "tipo": tipo,
                       "inicio": hora(inicio), "fin": hora(fin),
                       "duracion_s": None if abierto else round(fin - inicio),
                       "detectado": hora(detectado),
                       "retraso_deteccion_s": round(detectado - inicio) if detectado else None,
                       "se_recupero_solo": not abierto, "sin_resolver": abierto,
                       "evidencia": evidencia, "_inicio": inicio, **extra})

    # sin latido: huecos en lo recibido, incluido el principio y el final de la ventana
    marcas = [desde] + [f["recibido"] for f in filas] + [hasta]
    for i in range(1, len(marcas)):
        a, b = marcas[i - 1], marcas[i]
        if b - a <= HUECO:
            continue
        previo = filas[i - 2] if i >= 2 else None
        siguiente = filas[i - 1] if i - 1 < len(filas) else None
        al_cierre = siguiente is None
        evidencia = [f"Ningún latido recibido de {hora(a)} a {hora(b)} ({round(b - a)} s; se esperaba uno cada {INTERVALO} s)."]
        clase = "sin latido"
        if previo and siguiente:
            perdidos = siguiente["seq"] - previo["seq"] - 1 if siguiente["arranque"] == previo["arranque"] else None
            if siguiente["arranque"] != previo["arranque"]:
                clase = "servicio reiniciado"
                evidencia.append(f"El latido siguiente viene de un proceso nuevo, arrancado a las {hora(siguiente['arranque'])}.")
                caidas = [v for v in vigilante if v.get("evento") == "caida" and a <= v["t"] <= b]
                for v in caidas:
                    evidencia.append(f"El vigilante del equipo registró la caída del proceso a las {hora(v['t'])} (código {v.get('codigo')}).")
            else:
                no_env = siguiente.get("no_enviados", 0) - previo.get("no_enviados", 0)
                evidencia.append(f"Mismo proceso antes y después; faltan {perdidos} latidos en la secuencia.")
                if no_env and no_env >= perdidos:
                    clase = "el equipo no envió"
                    evidencia.append(f"El propio equipo registró {no_env} latidos como no enviados en ese lapso.")
                elif perdidos:
                    clase = "latidos perdidos en el camino"
                    evidencia.append(f"El equipo registró {no_env} como no enviados; {perdidos - no_env} salieron y no llegaron.")
        elif al_cierre:
            evidencia.append("Al cierre de la ventana seguía sin llegar ningún latido.")
        nuevo(clase, a, None if al_cierre else b, a + HUECO, evidencia)

    con_retraso = [f for f in filas if f.get("enviado")]
    if con_retraso:
        base = statistics.median(f["recibido"] - f["enviado"] for f in con_retraso)
        for tramo in rachas(con_retraso, lambda f: f["recibido"] - f["enviado"] - base > 2):
            peor = max(f["recibido"] - f["enviado"] - base for f in tramo)
            fin = None if tramo[-1] is filas[-1] and hasta - tramo[-1]["recibido"] < HUECO else tramo[-1]["recibido"]
            nuevo("latencia", tramo[0]["recibido"], fin, tramo[2]["recibido"],
                  [f"{len(tramo)} latidos seguidos llegaron con retraso: hasta {peor:.1f} s por encima de lo normal de la noche ({base:.2f} s)."])

    reglas = [
        ("saturación de CPU", lambda f: f.get("carga1", 0) > 0.75 * (f.get("cpus") or 1),
         lambda t: f"Carga de 1 minuto entre {min(x['carga1'] for x in t):.2f} y {max(x['carga1'] for x in t):.2f} con {t[0].get('cpus')} núcleos, en {len(t)} latidos seguidos."),
        ("memoria baja", lambda f: f.get("mem_total_mb") and f["mem_disp_mb"] < 0.2 * f["mem_total_mb"],
         lambda t: f"Memoria disponible entre {min(x['mem_disp_mb'] for x in t)} y {max(x['mem_disp_mb'] for x in t)} MB de {t[0]['mem_total_mb']} MB, en {len(t)} latidos seguidos."),
        ("temperatura alta", lambda f: (f.get("temp_c") or 0) > 80,
         lambda t: f"Temperatura hasta {max(x['temp_c'] for x in t):.1f} °C en {len(t)} latidos seguidos."),
    ]
    for tipo, condicion, texto in reglas:
        for tramo in rachas(filas, condicion):
            fin = None if tramo[-1] is filas[-1] and hasta - tramo[-1]["recibido"] < HUECO else tramo[-1]["recibido"]
            nuevo(tipo, tramo[0]["recibido"], fin, tramo[2]["recibido"], [texto(tramo)])
    return salida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=float)
    ap.add_argument("--hasta", type=float)
    ap.add_argument("--nombre")
    a = ap.parse_args()
    desde, hasta = (a.desde, a.hasta) if a.desde else ventana_de_anoche()
    nombre = a.nombre or f"noche-{dia(hasta)}"

    recibidos = [f for f in leer_jsonl(archivos("recibidos", desde, hasta)) if desde <= f["recibido"] <= hasta]
    vigilante = [v for v in leer_jsonl(archivos("vigilante", desde, hasta)) if desde <= v["t"] <= hasta]
    esperados = int((hasta - desde) // INTERVALO)

    equipos, incidentes = [], []
    for equipo in EQUIPOS:
        filas = sorted((f for f in recibidos if f.get("equipo") == equipo), key=lambda f: f["recibido"])
        propios = vigilante if equipo == "israel-MINI-N100C" else []
        inc = incidentes_de(equipo, filas, desde, hasta, propios)
        incidentes += inc
        llegados = len(filas)
        pct = round(100 * llegados / esperados, 1) if esperados else 0
        temps = [f["temp_c"] for f in filas if f.get("temp_c") is not None]
        equipos.append({
            "equipo": NOMBRE[equipo], "latidos_esperados": esperados, "latidos_recibidos": llegados,
            "porcentaje_recibido": pct, "incidentes": len(inc),
            "carga1_max": round(max((f["carga1"] for f in filas), default=0), 2),
            "mem_disp_min_mb": min((f["mem_disp_mb"] for f in filas), default=None),
            "temp_max_c": round(max(temps), 1) if temps else None,
            "salud": "buena" if pct >= 99 and not inc else "regular" if pct >= 95 and not any(i["sin_resolver"] for i in inc) else "mala",
        })
    incidentes.sort(key=lambda i: i.pop("_inicio"))
    for n, i in enumerate(incidentes, 1):
        i["id"] = n

    peor = min((e["salud"] for e in equipos), key=["mala", "regular", "buena"].index, default="mala")
    informe = {
        "noche": {"desde": time.strftime("%Y-%m-%d %H:%M", time.localtime(desde)),
                  "hasta": time.strftime("%Y-%m-%d %H:%M", time.localtime(hasta))},
        "salud_general": peor, "equipos": equipos, "incidentes": incidentes,
        "sin_resolver": [i["id"] for i in incidentes if i["sin_resolver"]],
        "reglas": {"hueco_s": HUECO, "intervalo_s": INTERVALO,
                   "latencia_s_sobre_mediana": 2, "cpu_fraccion_nucleos": 0.75,
                   "memoria_fraccion_minima": 0.2, "temperatura_c": 80, "latidos_seguidos": 3},
    }
    anterior = sorted(p for p in INFORMES.glob("noche-*.json") if p.stem < nombre)
    if anterior:
        prev = json.loads(anterior[-1].read_text())
        informe["comparacion"] = {
            "noche_anterior": prev["noche"],
            "salud_anterior": prev["salud_general"],
            "incidentes_anterior": len(prev["incidentes"]),
            "porcentaje_recibido_anterior": {e["equipo"]: e["porcentaje_recibido"] for e in prev["equipos"]},
        }
    destino = INFORMES / f"{nombre}.json"
    destino.write_text(json.dumps(informe, ensure_ascii=False, indent=2))
    print(destino)


if __name__ == "__main__":
    main()
