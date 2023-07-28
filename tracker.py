from loader import SatLoader
from orbit_predictor.predictors import TLEPredictor
import datetime as dt

MAX_SIMULTANEOUS_THREADS = 2

loader = SatLoader()
track_list = loader.get_tracked_list()
tles = loader.get_tle_db()
loc = loader.get_location()

pred_db = []
pass_db = []

for t_sat in track_list:
    p = tles.get_predictor(t_sat.get_id())
    pred_db.append(p)

for p in pred_db:
    satpass = p.get_next_pass(loc, max_elevation_gt=loader.min_elev)
    print("SATPASS\n")
    print("ID: ", satpass.sate_id)
    print("NAME: ", tles.get_name_from_id(satpass.sate_id))
    print("DURATION (seg): ", satpass.duration_s)
    print("AOS (UTC -3): ", satpass.aos.replace(tzinfo = dt.timezone.utc).astimezone(None))
    print("LOS (UTC -3): ", satpass.los.replace(tzinfo = dt.timezone.utc).astimezone(None))
    print("MAX-EL: ", satpass.max_elevation_deg)