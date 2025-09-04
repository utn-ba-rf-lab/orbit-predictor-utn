from loader import SatLoader
from orbit_predictor.predictors import TLEPredictor
import datetime as dt
import asyncio
import time
import concurrent.futures
import subprocess
import logging

# Configure logging to a file
logging.basicConfig(filename='orbit_predictor_logger.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
        if p.aos < last.los:
            logger.info(f"[+] Colisión de pasadas encontrada: {p.sate_id} y {last.sate_id}")
            logger.debug(f"    Tiempo de arranque de {p.sate_id}: {p.aos}")
            logger.debug(f"    Tiempo de finalización de {last.sate_id}: {last.aos}")
            logger.debug(f"    Elevación y preferencia de {p.sate_id}: {p.max_elevation_deg} | {track_list[p.sate_id].get_priority()}")
            logger.debug(f"    Elevación y preferencia de {last.sate_id}: {last.max_elevation_deg} | {track_list[last.sate_id].get_priority()}")
            # Hay superposición, elegimos el de mayor elevación
            if p.max_elevation_deg > last.max_elevation_deg or (
                track_list[p.sate_id].get_priority() > track_list[last.sate_id].get_priority()
            ):
                logger.info(f"    Se prefiere al satélite: {p.sate_id}")
                filtered[-1] = p  # reemplazamos al último
            # si no, simplemente descartamos este
            else: logger.info(f"    Se prefiere al satélite: {last.sate_id}")
        else:
            filtered.append(p)

    return filtered

def pass_worker(name:str, aos:dt.datetime, cmd_line:str) -> subprocess.CompletedProcess:
    sleep_t = aos.astimezone(tz=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc) - LAUNCH_BEFORE_SECS
    sleep_t = sleep_t.total_seconds()    
    # time.sleep(sleep_t)
    time.sleep(10)
    logger.debug(f"{sleep_t} segundos más tarde: ")
    ret_code = subprocess.run(args=[cmd_line])
    return ret_code

async def main() -> None:
    # Carga el SatLoader del paquete.
    loader = SatLoader()
    # Consigue la lista de satélites a observar.
    track_list = loader.get_tracked_list()
    # Consigue los ultimos TLEs de la base de datos.
    tles = loader.get_tle_db()
    # Consigue la ubicación actual de la configuración.
    loc = loader.get_location()

    loop = asyncio.get_running_loop()

    pred_db = []
    task_list = []

    # Por cada satélite observado, se consigue su predictór de la base de datos.
    for t_sat in track_list.values():
        p = tles.get_predictor(t_sat.get_id())
        pred_db.append(p)

    next_pass_date = 0

    # Comienza el loop infinito.
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_AWAITABLE_PASSES) as process_loop:
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
                        logger.info(f"    AOS: {satpass.aos.astimezone(tz=dt.timezone.utc)}")
                        logger.info(f"    LOS: {satpass.los.astimezone(tz=dt.timezone.utc)}")
                        logger.info(f"    Elevación máxima: {satpass.max_elevation_deg:.1f}°")
                        logger.info("-" * 50)
                        candidates.append(satpass)

                # Filtramos para evitar solapamientos
                filtered_passes = filter_overlapping_passes(candidates, track_list)

                next_pass_date = filtered_passes[-1].los.astimezone(tz=dt.timezone.utc)
                # Si se encontraron pasadas se calcula el tiempo de ejecución y se prepara un worker para ejecutar un script en la pasada.
                for p in filtered_passes:
                    time = p.aos
                    cmdline = track_list[p.sate_id].get_script()

                    logger.info(f"[+] Planificando el siguiente script a ejecutar del satélite: {p.sate_id}")
                    logger.info(f"    Script a ejecutar: {cmdline}")

                    task_future = loop.run_in_executor(process_loop, pass_worker, p.sate_id, time, cmdline)
                    task_list.append(task_future)

            done, pending = await asyncio.wait(task_list, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                task_list.remove(task)
        
if (__name__ == '__main__'):
    asyncio.run(main(), debug=True)
