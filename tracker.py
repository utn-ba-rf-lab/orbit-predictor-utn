from loader import SatLoader
from util_types import SatPass
import datetime as dt
import asyncio


MAX_AWAITABLE_PASSES = 5
LAUNCH_BEFORE_SECS = dt.timedelta(seconds=10)
UPDATE_TLE_SECS = dt.timedelta(weeks=1)
TEST_FILE="orbit_predictor.txt"


class Tracker:

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(Tracker, cls).__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        self._loader = SatLoader()
        self._location = self._loader.get_location()
        self._tracked_list = self._loader.get_tracked_list()
        self._min_elev = self._loader.get_minimal_elevation()
        self._last_update_time_utc = None
        self._tle_db = []
        self._predictor_db = []

        self._worker_sem = asyncio.BoundedSemaphore(value = MAX_AWAITABLE_PASSES)

        self.update_tle_srcs()

    async def run_w_testfile(self) -> None:

        testfile = open(TEST_FILE, "at")

        w_lock = asyncio.Lock()

        earlier_pass_date_utc = dt.datetime.now(tz=dt.timezone.utc)

        while (True) :

            if (not self._worker_sem.locked()):
                #launch worker
                await self._worker_sem.acquire()
                next_pass = self.get_next_pass(earlier_pass_date_utc)
                earlier_pass_date_utc = next_pass.aos
                asyncio.create_task(pass_worker_w_file(next_pass, self._worker_sem, testfile, w_lock))
                
            else:
                #wait for worker release or timeout to update TLE's DB
                upd_timeout = self._last_update_time_utc + UPDATE_TLE_SECS - dt.datetime.now(tz=dt.timezone.utc)
                try:
                    #await and immediate release so as not to consume
                    #the available slot for running another worker.
                    await asyncio.wait_for(self._worker_sem.acquire(), timeout=upd_timeout.total_seconds())
                    self._worker_sem.release()
                except asyncio.exceptions.TimeoutError:
                    #update TLE DB
                    self.update_tle_srcs()
                    testfile.write("[" + str(dt.datetime.now()) + "] ")
                    testfile.write("Updated TLE Database! \r\n")

    def update_tle_srcs(self) -> None:
        
        self._tle_db = self._loader.get_tle_db()
        self._predictor_db.clear()

        for t_sat in self._tracked_list.keys():
            pred = self._tle_db.get_predictor(t_sat)
            self._predictor_db.append(pred)

        self._last_update_time_utc = dt.datetime.now(tz=dt.timezone.utc)

    def get_next_pass(self, when_utc:dt.datetime):

        candidate_pass = None

        for pred in self._predictor_db:
            satpass = pred.get_next_pass(self._location, max_elevation_gt=self._min_elev, when_utc=when_utc)
            aos_utc = satpass.aos.astimezone(tz=dt.timezone.utc)

            if (candidate_pass is None):
                candidate_pass = satpass
            else:
                if (aos_utc < candidate_pass.aos.astimezone(tz=dt.timezone.utc)):
                    candidate_pass = satpass

        if not (candidate_pass is None):
            pass_obj = SatPass(candidate_pass, 
                               self._tle_db.get_name_from_id(candidate_pass.sate_id),
                               candidate_pass.aos,
                               candidate_pass.los,
                               self._tracked_list[candidate_pass.sate_id]["freq"],
                               self._tracked_list[candidate_pass.sate_id]["cmd"])
            return pass_obj
        
        return None


async def pass_worker_w_script(work_item, finish_sem):
    aos = work_item["aos"]
    freq = work_item["freq"]
    cmdline = work_item["cmd"]
    name = work_item["name"]
    sleep_t = aos.astimezone(tz=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc) - LAUNCH_BEFORE_SECS
    sleep_t = sleep_t.total_seconds()

    await asyncio.sleep(sleep_t)

    proc = await asyncio.create_subprocess_exec(cmdline, str("SAT " + name + " will pass above us in " + str(LAUNCH_BEFORE_SECS) + " secs!\n"))
    await proc.wait()

    finish_sem.release()


async def pass_worker_w_file(work_item:SatPass, finish_sem, test_file, w_lock):

    if not (work_item is None):
        sleep_t = work_item.aos.astimezone(tz=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc) - LAUNCH_BEFORE_SECS
        sleep_t = sleep_t.total_seconds()

        # print("Worker info: ")
        # print("AOS (UTC): ", aos.astimezone(tz=dt.timezone.utc))
        # print("deltaT: ", sleep_t)
        # print("Freq: ", freq)
        # print("CMD: ", cmdline)
        # print("###\n\n")

        await asyncio.sleep(2)

        async with w_lock:
            test_file.write("[" + str(dt.datetime.now()) + "] ")
            test_file.write("SAT: " + work_item.name + ", ")
            test_file.write("AOS (LOCAL): " + str(work_item.aos) + ", ")
            test_file.write("LOS (LOCAL): " + str(work_item.los) + ", ")
            test_file.write("f: " + str(work_item.freq) + " MHz, ")
            test_file.write("cmd: \"" + str(work_item.cmd) + "\" ")
            test_file.write("Will pass above us in 10 secs \r\n")    

        finish_sem.release()


tracker = Tracker()
asyncio.run(tracker.run_w_testfile())


