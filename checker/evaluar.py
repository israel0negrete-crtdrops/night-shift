#!/usr/bin/env python3
"""Evalúa una noche: lo provocado contra lo detectado, y cada reporte contra su JSON.

    python3 evaluar.py noche-2026-10-22            # baja los archivos de los dos equipos y evalúa
    python3 evaluar.py noche-2026-10-22 --local    # sólo evalúa lo que ya está en resultados/

Corre en la Mac. Deja todo en resultados/<noche>/ (JSON, los dos Markdown, sus
mediciones, la verdad de cada equipo) y escribe evaluacion.json.

Detección (contra datos/verdad-*.jsonl, que el detector nunca leyó):
  una falla cuenta como detectada si hay un incidente del equipo afectado que
  empieza entre 60 s antes y 90 s después de la falla; se mide el retraso de
  detección y la diferencia de duración. Incidentes sin falla = falsas alarmas.

Reporte (cada Markdown contra el JSON que recibió):
  - incidentes del JSON cuya hora de inicio no aparece en el reporte (omitidos);
  - horas y cifras del reporte que no están en el JSON (inventadas);
  - "Causa confirmada" con algo distinto de "no confirmada";
  - calificativos ("elevada", "alta", "inestable"...) sin un incidente que los respalde;
  - comparación con la noche anterior omitida o inventada.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EQUIPOS = {"edgelab-n100": "israel-MINI-N100C", "edgelab-rpi5": "pios"}
COMPATIBLES = {  # qué tipos del detector cuentan como haber visto cada falla
    "interrupcion": ("servicio reiniciado", "sin latido"),
    "pausa": ("servicio reiniciado", "sin latido"),
    "silencio": ("el equipo no envió", "latidos perdidos en el camino", "sin latido"),
    "corte": ("latidos perdidos en el camino", "el equipo no envió", "sin latido"),
    "latencia": ("latencia",),
    "cpu": ("saturación de CPU",),
    "memoria": ("memoria baja",),
}
CALIFICATIVOS = re.compile(r"\b(elevad[oa]s?|alt[oa]s?|inestab\w*|preocupa\w*|anormal\w*|crític[oa]s?|excesiv[oa]s?)\b", re.I)


def bajar(noche, destino):
    destino.mkdir(parents=True, exist_ok=True)
    d0, d1 = noche.removeprefix("noche-"), None
    for ssh, equipo in EQUIPOS.items():
        subprocess.run(["scp", "-q", f"{ssh}:turno/exp/informes/{noche}.*", str(destino)], check=False)
        subprocess.run(["sh", "-c", f"ssh -n {ssh} 'cat ~/turno/exp/datos/verdad-*.jsonl 2>/dev/null' > {destino}/verdad-{equipo}.jsonl"], check=False)


def jsonl(ruta):
    try:
        return [json.loads(l) for l in open(ruta) if l.strip()]
    except FileNotFoundError:
        return []


def hhmm(t):
    return time.strftime("%H:%M:%S", time.localtime(t))


def a_segundos(dia_hasta, hms, desde_ts):
    """HH:MM:SS del JSON -> epoch, dentro de la ventana de la noche."""
    h, m, s = map(int, hms.split(":"))
    for base in (desde_ts, desde_ts + 86400):
        t = time.mktime(time.strptime(time.strftime("%Y-%m-%d", time.localtime(base)) + f" {h}:{m}:{s}", "%Y-%m-%d %H:%M:%S"))
        if desde_ts - 120 <= t <= desde_ts + 9 * 3600:
            return t
    return None


def evaluar_deteccion(informe, verdades):
    desde = time.mktime(time.strptime(informe["noche"]["desde"], "%Y-%m-%d %H:%M"))
    hasta = time.mktime(time.strptime(informe["noche"]["hasta"], "%Y-%m-%d %H:%M"))
    incs = []
    for i in informe["incidentes"]:
        incs.append({**i, "_t": a_segundos(None, i["inicio"], desde),
                     "_d": a_segundos(None, i["detectado"], desde) if i.get("detectado") else None})
    usados, filas = set(), []
    for v in sorted((v for v in verdades if desde <= v["inicio"] <= hasta), key=lambda v: v["inicio"]):
        afectado = v.get("afectado", v["equipo_real"])
        fin_v = v.get("fin") or v["inicio"]
        cand = [i for i in incs if i["equipo"] == afectado and i["id"] not in usados and i["_t"]
                and i["tipo"] in COMPATIBLES.get(v["escenario"], ())
                and v["inicio"] - 60 <= i["_t"] <= max(v["inicio"] + 180, fin_v)]
        fila = {"escenario": v["escenario"], "equipo": afectado, "inicio": hhmm(v["inicio"]),
                "fin": hhmm(v["fin"]) if v.get("fin") else None,
                "duracion_real_s": round(v["fin"] - v["inicio"]) if v.get("fin") else None,
                "esperado": v.get("esperado"), "detectado": bool(cand)}
        if cand:
            i = min(cand, key=lambda i: abs(i["_t"] - v["inicio"]))
            usados.add(i["id"])
            fila.update(incidente=i["id"], tipo_detectado=i["tipo"],
                        retraso_deteccion_s=round(i["_d"] - v["inicio"]) if i["_d"] else None,
                        duracion_detectada_s=i.get("duracion_s"), sin_resolver=i.get("sin_resolver"))
        filas.append(fila)
    falsas = [{"id": i["id"], "equipo": i["equipo"], "tipo": i["tipo"], "inicio": i["inicio"]}
              for i in incs if i["id"] not in usados]
    return filas, falsas


def numeros(texto):
    """Cifras como números (100, 100.0 y 100% son la misma)."""
    return {float(n.replace(",", "")) for n in re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?", texto)}


def evaluar_reporte(md, informe):
    crudo = json.dumps(informe, ensure_ascii=False)
    horas_json = set(re.findall(r"\b\d{2}:\d{2}(?::\d{2})?\b", crudo))
    horas_json |= {h[:5] for h in horas_json}
    nums_json = numeros(crudo)
    cuerpo = md.split("\n", 1)[1] if "\n" in md else md          # sin el título
    horas_md = set(re.findall(r"\b\d{2}:\d{2}(?::\d{2})?\b", cuerpo))
    horas_inv = sorted(h for h in horas_md if h not in horas_json)
    nums_md = {n for n in numeros(re.sub(r"\b\d{2}:\d{2}(?::\d{2})?\b|\d{4}-\d{2}-\d{2}", " ", cuerpo))}
    nums_inv = sorted(n for n in nums_md if n not in nums_json and n >= 10)
    omitidos = [i["id"] for i in informe["incidentes"] if i["inicio"] not in md and i["inicio"][:5] not in md]
    causas = []
    for l in md.splitlines():
        m = re.search(r"causa confirmada\W*[:\-]\s*(.+)", l, re.I)
        if m and not re.search(r"no confirmada|ninguna|sin confirmar|no se confirm", m.group(1), re.I):
            causas.append(l.strip())
    tipos = {i["tipo"] for i in informe["incidentes"]}
    calif = sorted({m.group(0).lower() for m in CALIFICATIVOS.finditer(cuerpo)}) \
        if not tipos & {"saturación de CPU", "memoria baja", "temperatura alta", "latencia"} else []
    sin_incidentes_dice = bool(re.search(r"no hubo incidentes|sin incidentes", md, re.I))
    hay = bool(informe["incidentes"])
    comparacion = "comparacion" in informe
    dice_sin_anterior = bool(re.search(r"sin noche anterior", md, re.I))
    return {
        "incidentes_json": len(informe["incidentes"]),
        "incidentes_omitidos": omitidos,
        "dice_sin_incidentes": sin_incidentes_dice,
        "inventa_incidentes": (not hay) and bool(re.search(r"equipo[:\s]", md, re.I)) and not sin_incidentes_dice,
        "horas_inventadas": horas_inv, "cifras_inventadas": nums_inv,
        "causas_afirmadas": causas, "calificativos_sin_respaldo": calif,
        "comparacion_omitida": comparacion and dice_sin_anterior,
        "comparacion_inventada": (not comparacion) and not dice_sin_anterior,
    }


def main():
    noche = sys.argv[1]
    destino = AQUI / "resultados" / noche
    if "--local" not in sys.argv:
        bajar(noche, destino)
    informe = json.loads((destino / f"{noche}.json").read_text())
    verdades = jsonl(destino / "verdad-israel-MINI-N100C.jsonl") + jsonl(destino / "verdad-pios.jsonl")
    deteccion, falsas = evaluar_deteccion(informe, verdades)
    reportes = {}
    for equipo in EQUIPOS.values():
        md = destino / f"{noche}.{equipo}.md"
        med = destino / f"{noche}.{equipo}.medicion.json"
        if md.exists():
            reportes[equipo] = {**evaluar_reporte(md.read_text(), informe),
                                "medicion": json.loads(med.read_text()) if med.exists() else None}
    resultado = {"noche": informe["noche"], "salud_general": informe["salud_general"],
                 "fallas": deteccion, "falsas_alarmas": falsas, "reportes": reportes}
    (destino / "evaluacion.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2))

    print(f"{noche}: {len(deteccion)} fallas provocadas, {sum(f['detectado'] for f in deteccion)} detectadas, "
          f"{len(falsas)} falsas alarmas")
    for f in deteccion:
        print(f"  {f['inicio']} {f['equipo']:15} {f['escenario']:12} -> "
              + (f"{f['tipo_detectado']} (retraso {f['retraso_deteccion_s']} s; real {f['duracion_real_s']} s, detectada {f['duracion_detectada_s']} s)"
                 if f["detectado"] else "NO DETECTADA"))
    for e, r in reportes.items():
        m = r["medicion"] or {}
        print(f"  reporte {e}: {m.get('total_s')} s · omitidos {r['incidentes_omitidos']} · horas inventadas "
              f"{r['horas_inventadas']} · cifras inventadas {r['cifras_inventadas']} · causas {len(r['causas_afirmadas'])} · "
              f"calificativos {r['calificativos_sin_respaldo']} · inventa incidentes {r['inventa_incidentes']} · "
              f"comparación omitida {r['comparacion_omitida']} / inventada {r['comparacion_inventada']}")


if __name__ == "__main__":
    main()
