from loader import SatLoader
from util_types import SatPass
from dateutil import relativedelta
import datetime as dt
import asyncio


MAX_AWAITABLE_PASSES =  5
LAUNCH_BEFORE_SECS =    10
LAUNCH_AFTER_SECS =     10
UPDATE_TLE_SECS =       dt.timedelta(weeks=1)
TEST_FILE =             "orbit_predictor.txt"
DEBUG_CMD =             'test_script.sh'


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

        self.update_tle_srcs()

    async def run(self) -> None:

        worker_list = {}


        while (True):

            earliest_pass = dt.datetime.now(tz=dt.timezone.utc)
            pass_ignore = [int(x) for x in worker_list.keys()]
            next_pass = self.get_next_pass(earliest_pass, pass_ignore)

            if (next_pass is not None and len(worker_list) < MAX_AWAITABLE_PASSES):
                worker_list[str(next_pass.id)] = asyncio.create_task(pass_worker(next_pass))

            else:
                done, pending = await asyncio.wait(worker_list.values(), return_when=asyncio.FIRST_COMPLETED)
                
                if (len(done) > 0):
                    for key, value in list(worker_list.items()):
                        if value in done:
                            worker_list.pop(key)
                else :
                    self.update_tle_srcs()

    def update_tle_srcs(self) -> None:
        
        self._tle_db = self._loader.get_tle_db()
        self._predictor_db.clear()

        for t_sat in self._tracked_list.keys():
            pred = self._tle_db.get_predictor(t_sat)
            self._predictor_db.append(pred)

        self._last_update_time_utc = dt.datetime.now(tz=dt.timezone.utc)

    def get_next_pass(self, when_utc:dt.datetime, ignore_list:list[int]) -> SatPass:

        candidate_pass = None

        for pred in self._predictor_db:
            satpass = pred.get_next_pass(self._location, max_elevation_gt=self._min_elev, when_utc=when_utc)
            if not (ignore_list is None):
                if satpass.sate_id in ignore_list:
                    continue

            aos_utc = satpass.aos.astimezone(tz=dt.timezone.utc)

            if (candidate_pass is None):
                candidate_pass = satpass
            else:
                if (aos_utc < candidate_pass.aos.astimezone(tz=dt.timezone.utc)):
                    candidate_pass = satpass

        if not (candidate_pass is None):
            pass_obj = SatPass(candidate_pass.sate_id, 
                               self._tle_db.get_name_from_id(candidate_pass.sate_id),
                               candidate_pass.aos,
                               candidate_pass.los,
                               self._tracked_list[candidate_pass.sate_id]["cmd"])
            return pass_obj
        
        return None

class TrackerDebug(Tracker):

    def __init__(self) -> None:
        super().__init__()

    def __new__(cls):
        return super().__new__(cls)
    
    def get_next_pass(self, when_utc: dt.datetime, ignore_list: list[int]) -> SatPass:
        
        if (len(ignore_list) == 0):
            debugnum = 999999
        else :
            debugnum = int(ignore_list[-1]) - 1
        
        debugpass = SatPass(str(debugnum),
                            'DEBUG_SAT',
                            when_utc + relativedelta.relativedelta(seconds=20),
                            when_utc + relativedelta.relativedelta(seconds=40),
                            DEBUG_CMD)
        return debugpass
    
    def run(self) -> any:
        return super().run()


async def pass_worker(satpass:SatPass):

    aos = satpass.aos
    los = satpass.los
    cmdline = satpass.cmd
    name = satpass.name
    sleep_t = aos.astimezone(tz=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc)
    sleep_t = sleep_t.total_seconds() - LAUNCH_BEFORE_SECS

    await asyncio.sleep(sleep_t)

    proc = await asyncio.create_subprocess_exec(cmdline, str("SAT " + name + " will pass above us in " + str(LAUNCH_BEFORE_SECS) + " secs!\n"))

    sleep_t = los.astimezone(tz=dt.timezone.utc) - dt.datetime.now(dt.timezone.utc)
    sleep_t = sleep_t.total_seconds() + LAUNCH_AFTER_SECS

    await asyncio.sleep(sleep_t)

    await proc.terminate()

tracker = TrackerDebug()
asyncio.run(tracker.run())


