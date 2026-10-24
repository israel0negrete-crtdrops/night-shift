# night-shift

Two lab machines watch each other overnight. Fixed rules decide what happened;
Gemma 3 4B, running locally in Ollama, only writes the morning report. Nothing
leaves the lab and nothing needs the internet.

This is the code exactly as it ran on an Intel N100 mini PC and a Raspberry Pi 5
from October 19 to 24, 2026, with the fault plans, the reports Gemma wrote and the
checker that graded them. It is not a cleaned-up version: names, comments and
the report prompt are in Spanish, as they ran.

The write-up: [Night shift: a local Gemma writes my 7 a.m. lab report, and I
measured where it makes things up](https://crtdrops.mx/notas/night-shift.html)
([en español](https://crtdrops.mx/notas/el-turno-de-noche.html)).

Built with Claude Code as a pair: Israel decided what to measure, what the lab
could and could not be put through, and what the report had to say; Claude
wrote most of the code and ran it on the machines with him.

## How it works

```
 every 10 s                                  6:30 a.m.                 6:30 / 6:40
 latido.py ──► intermediario.py ──► colector.py ──► detector.py ──► JSON ──► redactor.py ──► report.md
 (each machine)   (N100, :7701)       (N100)        fixed rules            Gemma 3 4B, local
       ▲                ▲
  vigilante.py     fallas.py injects controlled faults at fixed times;
  (restarts it)    the truth goes to datos/verdad-*.jsonl, which the detector never reads
```

| File | Runs on | What it does |
|---|---|---|
| `bin/latido.py` | both | heartbeat every 10 s: sequence, send time, process start time, load, memory, temperature, count of unsent heartbeats; also logged locally |
| `bin/vigilante.py` | both | restarts the heartbeat 30 s after it dies (like systemd's `Restart=`) |
| `bin/intermediario.py` | N100 | relay on :7701 for the experimental flow only; cut and latency faults are applied here |
| `bin/colector.py` | N100 | stores what arrives with the arrival time; serves the reports over HTTP on :7702 for the Pi |
| `bin/detector.py` | N100, 6:30 | fixed rules over 22:00–6:30; writes `informes/noche-<date>.json` |
| `bin/redactor.py` | both | Gemma 3 4B reads only that JSON and writes `<night>.<host>.md` plus timing in `<night>.<host>.medicion.json` |
| `bin/fallas.py` | both, 22:05 | runs a fault plan; logs what really happened to `datos/verdad-*.jsonl` |
| `bin/asegurar.sh` | both, every 5 min | starts whatever is not running (Ollama, collector, relay, watchdog) |
| `bin/manana.sh` | 6:30 N100, 6:40 Pi | detector and writer on the N100; on the Pi, fetches the JSON and writes its own report |
| `checker/evaluar.py` | a laptop | compares injected faults with detected incidents, and each report with its JSON |

Everything is standard-library Python 3 plus [Ollama](https://ollama.com). No
sudo, no system services touched.

### The detector's rules

- **No heartbeat:** more than 30 s without one. Classified by the next heartbeat:
  a new process start time means *service restarted*; the same process with
  heartbeats the machine itself logged as unsent means *the machine did not
  send*; the same process with heartbeats sent but never received means
  *heartbeats lost on the way*.
- **Latency:** arrival minus send time 2 s above the night's median, for 3 heartbeats in a row.
- **CPU:** one-minute load above 75 % of the cores, for 3 heartbeats in a row.
- **Memory:** under 20 % available, for 3 heartbeats in a row.
- **Temperature:** above 80 °C, for 3 heartbeats in a row.

### The writer

`gemma3:4b` (id `68ceab7e468a`, Q4_K_M) on Ollama 0.40.6, temperature 0, seed 42,
8,192-token context. The prompt (in `redactor.py`) tells it to use only the hours,
figures and facts in the JSON and to keep observed facts, possible explanations
and confirmed causes apart.

## Results

`results/` has one folder per night: the detector's JSON, each machine's report
and timing, the fault log, and the checker's `evaluacion.json`.

| Night | Folder | Faults | Detected | Notes |
|---|---|---:|---:|---|
| Oct 19–20, quiet | `noche-2026-10-20` | 0 | 0 | |
| Oct 20–21, quiet | `noche-2026-10-21` | 0 | 0 | |
| Oct 21–22, faults | `noche-2026-10-22` | 8 | 8 | |
| Oct 22–23, faults | `noche-2026-10-23` | 8 | 8 | plus a real high-temperature incident caused by the CPU fault (84 °C); the checker lists it as unplanned |
| Oct 21 afternoon test | `prueba-fallas` | rehearsal; two plans overlapped on the Pi | | |

Report folders are named after the morning they were written.

`results/crudos/` has the raw data of October 21 to 23, gzipped: what the collector
received on the N100 (`recibidos`), each machine's own heartbeat log
(`latido`) and its watchdog log (`vigilante`, only on the days it restarted
something).

The files in `bin/` are byte-for-byte the ones that ran on both machines
(checked with sha256 on October 24, 2026).

### Replaying the detector

The detector reads `~/turno/exp/datos`. Point `HOME` at a scratch folder, unpack
the N100's raw files there and run it over a night's window (Unix seconds; the
windows below are 22:00–06:30 in Mexico City, and the date logic uses the local
time zone):

```
mkdir -p /tmp/replay/turno/exp/datos /tmp/replay/turno/exp/informes
for f in results/crudos/n100/*.gz; do gunzip -c "$f" > /tmp/replay/turno/exp/datos/$(basename "$f" .gz); done
cp results/noche-2026-10-21/noche-2026-10-21.json /tmp/replay/turno/exp/informes/   # previous night, for the comparison
cd bin
TZ=America/Mexico_City HOME=/tmp/replay python3 detector.py --desde 1792641600 --hasta 1792672200 --nombre noche-2026-10-22
TZ=America/Mexico_City HOME=/tmp/replay python3 detector.py --desde 1792728000 --hasta 1792758600 --nombre noche-2026-10-23
```

The JSON it writes is identical to the one in `results/` for both fault nights.

## Running it on your own machines

The lab constants are hard-coded, as they ran. Change them before using it:

- `bin/comun.py`: `N100` (the collector's IP) and the ports.
- `bin/intermediario.py`: `EQUIPOS` maps each source IP to a hostname.
- `bin/detector.py` and `bin/fallas.py`: `EQUIPOS` / `NOMBRE`, the hostnames and their display names.
- `bin/latido.py`, `bin/asegurar.sh`, `bin/manana.sh`: the collector machine is recognized by its hostname.
- `checker/evaluar.py`: the SSH aliases of the two machines.

Everything lives under `~/turno/exp` (`bin/`, `datos/`, `control/`, `informes/`),
Ollama under `~/turno/ollama` and its models under `~/turno/modelos`. Then, in each
machine's user crontab:

```
*/5 * * * * $HOME/turno/exp/bin/asegurar.sh
@reboot     $HOME/turno/exp/bin/asegurar.sh
30 6 * * *  $HOME/turno/exp/bin/manana.sh     # 40 6 on the second machine
```

To write a report from one of the recorded nights with your own Ollama:

```
ollama pull gemma3:4b
python3 bin/redactor.py results/noche-2026-10-22/noche-2026-10-22.json
```

## License

Code: MIT (see `LICENSE`). Results and reports in `results/`: CC BY 4.0, by
Israel Negrete Lepe.
