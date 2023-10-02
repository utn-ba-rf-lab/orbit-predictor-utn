from loader import SatLoader
from loader import SatTrackCfg
from orbit_predictor.predictors import TLEPredictor
import datetime as dt
import asyncio
import subprocess

MAX_AWAITABLE_PASSES = 5
LAUNCH_BEFORE_SECS = dt.timedelta(seconds=10)
TEST_DIR="/tmp/orbit-predictor/"


class Tracker:

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(SatLoader, cls).__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        self._loader = SatLoader()
        self._location = self._loader.get_location()
        self._tracked_list = self._loader.get_tracked_list()
        self._tle_db = []
        self._predictor_db = []

        self._worker_sem = asyncio.BoundedSemaphore(value = MAX_AWAITABLE_PASSES)
        self._update_tle_sem = asyncio.BoundedSemaphore()

        self.update_tle_srcs()

    def update_tle_srcs(self) -> None:
        
        self._tle_db = self._loader.get_tle_db()
        self._predictor_db.clear()

        for t_sat in self._tracked_list.keys():
            pred = self._tle_db.get_predictor(t_sat)
            self._predictor_db.append(pred)

    def get_next_pass(self, when_utc:dt.datetime):

        candidate_pass = None

        for pred in self._predictor_db:
            satpass = pred.get_next_pass(self._location, max_elevation_gt=self._loader.get_minimal_elevation(), when_utc=when_utc)
            aos_utc = satpass.aos.astimezone(tz=dt.timezone.utc)

            if (candidate_pass is None):
                candidate_pass = satpass
            else:
                if (aos_utc < candidate_pass.aos.astimezone(tz=dt.datetime.utc)):
                    candidate_pass = satpass

        if not (candidate_pass is None):
            pass_obj = {
                "id" : candidate_pass.sate_id,
                "name" : self._tle_db.get_name_from_id(candidate_pass.sate_id),
                "aos" : candidate_pass.aos,
                "los" : candidate_pass.los,
                "freq" : self._tracked_list[candidate_pass.sate_id]["freq"],
                "cmd" : self._tracked_list[candidate_pass.sate_id]["cmd"]
            }
            return pass_obj
        
        return None




async def pass_worker(work_item, finish_sem):

    aos = work_item["aos"]
    freq = work_item["freq"]
    cmdline = work_item["cmdline"]
    name = work_item["name"]
    sleep_t = aos.astimezone(tz=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc) - LAUNCH_BEFORE_SECS
    sleep_t = sleep_t.total_seconds()

    # print("Worker info: ")
    # print("AOS (UTC): ", aos.astimezone(tz=dt.timezone.utc))
    # print("deltaT: ", sleep_t)
    # print("Freq: ", freq)
    # print("CMD: ", cmdline)
    # print("###\n\n")

    await asyncio.sleep(sleep_t)

    proc = await asyncio.create_subprocess_exec(cmdline, str("SAT " + name + " will pass above us in " + str(LAUNCH_BEFORE_SECS) + " secs!\n"))
    await proc.wait()

    finish_sem.release()


async def update_tle_worker(loader:SatLoader, track_list:list, tle_list:list, predictor_db:list, lock_sem:asyncio.BoundedSemaphore) -> None:

    
    while(True):
    
        await lock_sem.acquire()

        loader.update_tle_db()
        tle_list = loader.get_tle_db()
        predictor_db.clear()

        for t_sat in track_list.values():
            p = tle_list.get_predictor(t_sat.get_id())
            predictor_db.append(p)

        await lock_sem.release()

        await asyncio.sleep(86400)


async def main():

    task_count_sem = asyncio.BoundedSemaphore(value = MAX_AWAITABLE_PASSES)
    task_update_tle = asyncio.BoundedSemaphore()

    next_pass_date = dt.datetime.now(tz=dt.timezone.utc)

    

            

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


