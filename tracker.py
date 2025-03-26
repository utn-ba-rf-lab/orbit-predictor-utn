from loader import SatLoader
from loader import SatTrackCfg
from orbit_predictor.predictors import TLEPredictor
import datetime as dt
import asyncio
import time
import concurrent.futures
import subprocess

MAX_AWAITABLE_PASSES = 5
LAUNCH_BEFORE_SECS = dt.timedelta(seconds=10)

def pass_worker(name:str, aos:dt.datetime, cmd_line:str) -> subprocess.CompletedProcess:
    sleep_t = aos.astimezone(tz=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc) - LAUNCH_BEFORE_SECS
    sleep_t = sleep_t.total_seconds()    
    time.sleep(sleep_t)
    ret_code = subprocess.run(args=[cmd_line])
    return ret_code

async def main() -> None:
    loader = SatLoader()
    track_list = loader.get_tracked_list()
    tles = loader.get_tle_db()
    loc = loader.get_location()

    loop = asyncio.get_running_loop()

    pred_db = []
    task_list = []

    for t_sat in track_list.values():
        p = tles.get_predictor(t_sat.get_id())
        pred_db.append(p)

    next_pass_date = 0

    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_AWAITABLE_PASSES) as process_loop:
        while True:

            while (len(task_list) < MAX_AWAITABLE_PASSES):

                current_earlier_pass = None
                
                if (len(task_list) == 0):
                    next_pass_date = dt.datetime.now(tz=dt.timezone.utc)

                for p in pred_db:
                    satpass = p.get_next_pass(loc, max_elevation_gt=loader.min_elev, when_utc=next_pass_date)
                    aos_utc = satpass.aos.astimezone(tz=dt.timezone.utc)
                    if (current_earlier_pass is None):
                        current_earlier_pass = satpass
                    else:
                        if (aos_utc < current_earlier_pass.aos.astimezone(tz=dt.timezone.utc)):
                            current_earlier_pass = satpass

                if (not current_earlier_pass is None):
                    next_pass_date = current_earlier_pass.los.astimezone(tz=dt.timezone.utc)
                    time = current_earlier_pass.aos
                    cmdline = track_list[current_earlier_pass.sate_id].get_script()

                    task_future = loop.run_in_executor(process_loop, pass_worker, satpass.sate_id, time, cmdline)
                    task_list.append(task_future)

            done, pending = await asyncio.wait(task_list, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                task_list.remove(task)
        
if (__name__ == '__main__'):
    asyncio.run(main(), debug=True)
