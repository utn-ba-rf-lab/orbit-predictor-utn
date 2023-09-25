from loader import SatLoader
from loader import SatTrackCfg
from orbit_predictor.predictors import TLEPredictor
import datetime as dt
import asyncio
import subprocess

MAX_AWAITABLE_PASSES = 5
LAUNCH_BEFORE_SECS = dt.timedelta(seconds=10)

async def pass_worker(work_item, finish_sem):
    aos = work_item["aos"]
    freq = work_item["freq"]
    cmdline = work_item["cmdline"]
    sleep_t = aos.astimezone(tz=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc) - LAUNCH_BEFORE_SECS
    sleep_t = sleep_t.total_seconds()

    print("Worker info: ")
    print("AOS (UTC): ", aos.astimezone(tz=dt.timezone.utc))
    print("deltaT: ", sleep_t)
    print("Freq: ", freq)
    print("CMD: ", cmdline)
    print("###\n\n")

    await asyncio.sleep(5)
    finish_sem.release()


async def main():

    loader = SatLoader()
    track_list = loader.get_tracked_list()
    tles = loader.get_tle_db()
    loc = loader.get_location()

    pred_db = []
    task_list = []
    task_count_sem = asyncio.BoundedSemaphore(value = MAX_AWAITABLE_PASSES)

    print(track_list.values())

    for t_sat in track_list.values():
        p = tles.get_predictor(t_sat.get_id())
        pred_db.append(p)

    next_pass_date = 0

    while (True):
        
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

        if not (current_earlier_pass is None):
            next_pass_date = current_earlier_pass.los.astimezone(tz=dt.timezone.utc)
            time = current_earlier_pass.aos
            cmdline = track_list[satpass.sate_id].get_script()
            freq = track_list[satpass.sate_id].get_freq()
            work_obj = {"aos":time, "freq":freq, "cmdline":cmdline}
            await task_count_sem.acquire()
            task_list.append(asyncio.create_task(pass_worker(work_obj, task_count_sem)))
            

        # aos = satpass.aos
        # if (aos.tzinfo != None):
        #     aos = aos.astimezone(tz=None)
            
        # los = satpass.los
        # if (los.tzinfo != None):
        #     los = los.astimezone(tz=None)

        # print("SATPASS\n")
        # print("ID: ", satpass.sate_id)
        # print("NAME: ", tles.get_name_from_id(satpass.sate_id))
        # print("DURATION (seg): ", satpass.duration_s)
        # print("AOS (UTC -3): ", aos)
        # print("LOS (UTC -3): ", los)
        # print("MAX-EL: ", satpass.max_elevation_deg)

        

asyncio.run(main())


