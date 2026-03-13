from loader import SatLoader
from orbit_predictor.predictors import TLEPredictor
import datetime as dt
import asyncio
import time
import concurrent.futures
import subprocess
import logging
import sys

# Configurar el logger para que escriba a stdout (al journalctl).
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

MAX_AWAITABLE_PASSES = 5
LAUNCH_BEFORE_SECS = dt.timedelta(seconds=10)

def filter_overlapping_passes(passes, track_list):
    # Ordenamos por AOS
    passes = sorted(passes, key=lambda p: p.aos)

    filtered = []
    for p in passes:
        if not filtered:
            filtered.append(p)
            continue

        last = filtered[-1]

        # Chequear si se superponen
        if p.aos < last.los: # + dt.timedelta(hours=1):
            logger.info(f"[+] Colisión de pasadas encontrada: {p.sate_id} y {last.sate_id}")
            logger.debug(f"    Tiempo de arranque de {p.sate_id}: {p.aos}")
            logger.debug(f"    Tiempo de finalización de {last.sate_id}: {last.los}")
            logger.debug(f"    Elevación y preferencia de {p.sate_id}: {p.max_elevation_deg} | {track_list[p.sate_id].get_priority()}")
            logger.debug(f"    Elevación y preferencia de {last.sate_id}: {last.max_elevation_deg} | {track_list[last.sate_id].get_priority()}")
            # Hay superposición, elegimos el de mayor prioridad primero, y si empatan, el de mayor elevación
            if (track_list[p.sate_id].get_priority() > track_list[last.sate_id].get_priority() or
                (p.max_elevation_deg > last.max_elevation_deg and
                track_list[p.sate_id].get_priority() == track_list[last.sate_id].get_priority())):
                logger.info(f"    Se prefiere al satélite: {p.sate_id}")
                filtered[-1] = p  # reemplazamos al último
            # si no, simplemente descartamos este
            else: logger.info(f"    Se prefiere al satélite: {last.sate_id}")
        else:
            filtered.append(p)

    return filtered

async def pass_worker_async(p, track):
    delay = (p.aos - dt.datetime.now(dt.timezone.utc) - LAUNCH_BEFORE_SECS).total_seconds()
    await asyncio.sleep(max(0, delay))

    cmd = [
        track.get_script(),
        "--catnum", str(p.sate_id),
        "--priority", str(track.get_priority()),
        "--aos", p.aos.isoformat(),
        "--los", p.los.isoformat(),
        "--max-elev", str(p.max_elevation_deg)
    ]

    logger.info(f"[+] Ejecutando {p.sate_id}: {' '.join(cmd)}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    logger.info(f"[+] Finalizó {p.sate_id} con código de retorno: {proc.returncode}")
    if stdout:
        logger.info(f"    STDOUT:\n{stdout.decode('UTF-8')}")
    if stderr:
        logger.error(f"    STDERR:\n{stderr.decode('UTF-8')}")

def pass_worker(name:str, aos:dt.datetime, los:dt.datetime, cmd_line:str) -> subprocess.CompletedProcess:
    sleep_t = aos.astimezone(tz=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc) - LAUNCH_BEFORE_SECS
    sleep_t = max(0, sleep_t.total_seconds())
    time.sleep(sleep_t)

    logger.info(f"[+] Ejecutando script para satélite {name}")
    logger.info(f"    Comando: {cmd_line}")
    logger.info(f"    Fecha de arribo: {aos}")
    logger.info(f"    Fecha de finalización: {los}")
    
    resultado = subprocess.run(args=[cmd_line, name, aos, los])
    
    logger.info(f"[+] Script finalizado ({name}) código={resultado.returncode}")
    if resultado.stdout:
        logger.info(f"    STDOUT:\n{resultado.stdout}")
    if resultado.stderr:
        logger.error(f"    STDERR:\n{resultado.stderr}")

    return resultado

async def main() -> None:
    logger.info(f"[*] Inicializando componentes del orbit-predictor.")
    # Carga el SatLoader del paquete.
    loader = SatLoader()
    # Consigue la lista de satélites a observar.
    track_list = loader.get_tracked_list()
    # Consigue los ultimos TLEs de la base de datos.
    tles = loader.get_tle_db()
    # Consigue la ubicación actual de la configuración.
    loc = loader.get_location()

    logger.info(f"[*] Cargando satélites del cfg.json.")
    pred_db = []

    # Por cada satélite observado, se consigue su predictór de la base de datos.
    for t_sat in track_list.values():
        p = tles.get_predictor(t_sat.get_id())
        pred_db.append(p)

    task_list: list[asyncio.Task] = []

    next_pass_date = 0

    # Comienza el loop infinito.
    while True:
        # Mientras la lista tenga espacio disponible.
        while (len(task_list) < MAX_AWAITABLE_PASSES):
            current_earlier_pass = None
            
            # Si no hay tareas, calcular la próxima pasada desde ahora.
            if (len(task_list) == 0):
                next_pass_date = dt.datetime.now(tz=dt.timezone.utc)

            candidates = []

            # En cada predictór, nos fijamos la próxima pasada, pasamos su AOS a UTC-3.
            for p in pred_db:
                satpass = p.get_next_pass(loc, max_elevation_gt=loader.min_elev, when_utc=next_pass_date)
                if satpass is not None:
                    logger.info(f"[+] Próxima pasada encontrada: {satpass.sate_id}")
                    logger.info(f"    AOS: {satpass.aos.astimezone(tz=dt.timezone(dt.timedelta(hours=-3)))}")
                    logger.info(f"    LOS: {satpass.los.astimezone(tz=dt.timezone(dt.timedelta(hours=-3)))}")
                    logger.info(f"    Elevación máxima: {satpass.max_elevation_deg:.1f}°")
                    logger.info("-" * 50)
                    candidates.append(satpass)

            # Filtramos para evitar solapamientos
            filtered_passes = filter_overlapping_passes(candidates, track_list)

            # Actualizar punto de búsqueda
            next_pass_date = max(
                p.los.astimezone(dt.timezone.utc)
                for p in filtered_passes
            )

            # Si se encontraron pasadas se calcula el tiempo de ejecución y se prepara un worker para ejecutar un script en la pasada.
            for p in filtered_passes:
                track = track_list[p.sate_id]

                logger.info(f"[+] Planificando ejecución: {p.sate_id}")
                logger.info(f"    Script: {track.get_script()}")
                logger.info(f"    Prioridad: {track.get_priority()}")

                task = asyncio.create_task(
                    pass_worker_async(p, track)
                )

                task_list.append(task)
                
        done, pending = await asyncio.wait(task_list, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                await task
            except Exception as e:
                logger.exception(f"[x] Error en tarea: {e}")
            finally:
                task_list.remove(task)
        
if (__name__ == '__main__'):
    asyncio.run(main(), debug=True)
