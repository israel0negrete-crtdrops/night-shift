# Turno de noche: 2026-10-21 15:10
**Salud general:** mala. El 91.7% de los latidos recibidos provienen del equipo N100 y el 44.4% del Raspberry Pi 5.

## Incidentes
*   **N100:** servicio reiniciado, 15:11:16 - 15:11:50, 35s, detectado 15:11:46, no recuperado solo, no resuelto.
    Hechos observados: Ningún latido recibido de 15:11:16 a 15:11:50 (35 s; se esperaba uno cada 10 s). El latido siguiente viene de un proceso nuevo, arrancado a las 15:11:50. El vigilante del equipo registró la caída del proceso a las 15:11:20 (código -15). / Posibles explicaciones: no confirmada / Causa confirmada: no confirmada
*   **Raspberry Pi 5:** latidos perdidos en el camino, 15:11:19 - 15:13:07, 108s, detectado 15:11:49, no recuperado solo, no resuelto.
    Hechos observados: Ningún latido recibido de 15:11:19 a 15:13:07 (108 s; se esperaba uno cada 10 s). Mismo proceso antes y después; faltan 9 latidos en la secuencia. El equipo registró 7 como no enviados; 2 salieron y no llegaron. / Posibles explicaciones: no confirmada / Causa confirmada: no confirmada
*   **Raspberry Pi 5:** latencia, 15:13:07 - 15:14:27, 80s, detectado 15:13:27, no recuperado solo, no resuelto.
    Hechos observados: 9 latidos seguidos llegaron con retraso: hasta 8.0 s por encima de lo normal de la noche (0.01 s). / Posibles explicaciones: no confirmada / Causa confirmada: no confirmada
*   **Raspberry Pi 5:** saturación de CPU, 15:13:57 - 15:15:19, 82s, detectado 15:14:17, no recuperado solo, no resuelto.
    Hechos observados: Carga de 1 minuto entre 3.11 y 3.85 con 4 núcleos, en 10 latidos seguidos. / Posibles explicaciones: no confirmada / Causa confirmada: no confirmada
*   **N100:** memoria baja, 15:14:30 - 15:15:20, 50s, detectado 15:14:50, no recuperado solo, no resuelto.
    Hechos observados: Memoria disponible entre 1210 y 1217 MB de 7681 MB, en 6 latidos seguidos. / Posibles explicaciones: no confirmada / Causa confirmada: no confirmada
*   **Raspberry Pi 5:** servicio reiniciado, 15:15:19 - 15:20:00, 282s, detectado 15:15:49, no recuperado solo, no resuelto.
    Hechos observados: Ningún latido recibido de 15:15:19 a 15:20:00 (282 s; se esperaba uno cada 10 s). El latido siguiente viene de un proceso nuevo, arrancado a las 15:20:00. / Posibles explicaciones: no confirmada / Causa confirmada: no confirmada
*   **N100:** sin latido, 15:21:20 - 15:22:00, 39s, detectado 15:21:50, no recuperado solo, resuelto.
    Hechos observados: Ningún latido recibido de 15:21:20 a 15:22:00 (39 s; se esperaba uno cada 10 s). Al cierre de la ventana seguía sin llegar ningún latido. / Posibles explicaciones: no confirmada / Causa confirmada: no confirmada
*   **Raspberry Pi 5:** sin latido, 15:21:20 - 15:22:00, 39s, detectado 15:21:50, no recuperado solo, resuelto.
    Hechos observados: Ningún latido recibido de 15:21:20 a 15:22:00 (39 s; se esperaba uno cada 10 s). Al cierre de la ventana seguía sin llegar ningún latido. / Posibles explicaciones: no confirmada / Causa confirmada: no confirmada

## Sin resolver
*   N100 - sin latido (15:21:20 - 15:22:00)
*   Raspberry Pi 5 - sin latido (15:21:20 - 15:22:00)

## Recomendaciones
Verificar la estabilidad del proceso en N100. Investigar la causa de la pérdida de latidos en el Raspberry Pi 5.

## Comparación con la noche anterior
Sin noche anterior para comparar.
