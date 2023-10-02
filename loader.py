from sgp4 import omm
from sgp4.api import Satrec
from sgp4 import exporter
from orbit_predictor.sources import TLESource
from orbit_predictor.utils import datetime_from_jday
from orbit_predictor.locations import Location
from fetcher import SatTLEFetcher

from collections import defaultdict

import datetime as dt
import os
import json

DEFAULT_CFG_FILENAME = 'cfg.json'
DEFAULT_CFG_OBJ = {'global-params':{'min-elev': 40, 'loc-lat':0, 'loc-long':0, 'loc-elev':0},
                   'tracked-sats':[{'catnum':'33591',
                                    'freq':'0.0',
                                    'script':''}]
                    }
MAX_BYTESIZE = 8192

class CustomMemoryTLESource(TLESource):
    def __init__(self):
        self.db = defaultdict(dict)

    def add_tle(self, sate_id, tle, epoch, alias=None):
        if (alias != None):
            self.db[sate_id]['alias'] = alias
        elif (self.db[sate_id].get('alias', None) == None):  
            self.db[sate_id]['alias'] = ""

        if (self.db[sate_id].get('tles', None) == None):
            self.db[sate_id]['tles'] = set()
        
        self.db[sate_id]['tles'].add((epoch, tle))

    def _get_tle(self, sate_id, date):
        candidates = self.db[sate_id]['tles']
        print(candidates)
        winner = None
        winner_dt = float("inf")

        for epoch, candidate in candidates:
            c_dt = abs((epoch - date).total_seconds())
            if c_dt < winner_dt:
                winner = candidate
                winner_dt = c_dt

        if winner is None:
            raise LookupError("no tles in storage")

        return winner
    
    def get_name_from_id(self, sate_id) -> str:
        if (self.db.get(sate_id, None) != None):
            return self.db[sate_id].get('alias', "")
        return ""

class SatLoader():
    
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(SatLoader, cls).__new__(cls)
        return cls.instance
    
    def __init__(self, cfgfile=''):

        self.__satlist = {}

        if (cfgfile != '' and os.path.isfile(os.path.abspath(cfgfile))):
            self.__cfgfile = os.path.abspath(cfgfile)
        else:
            script_path = os.path.dirname(os.path.abspath(__file__))
            self.__cfgfile = os.path.join(script_path, DEFAULT_CFG_FILENAME)
            if not (os.path.isfile(self.__cfgfile)):
                with open(self.__cfgfile, 'w') as f:
                    json.dump(DEFAULT_CFG_OBJ, f, indent=4)

        with open(self.__cfgfile, 'r', encoding='utf-8') as f:
            contents = f.read(MAX_BYTESIZE)
            cfg = json.loads(contents)
        
        if (type(cfg) != dict):
            raise RuntimeError("Error! Root config entity is not a json object")
        
        self.__parse_global_params_from_json_obj(cfg.get('global-params', None))
        self.__parse_satlist_from_json_arr(cfg.get('tracked-sats', []))
        self.__load_tles_to_mem()
            

    def __parse_satlist_from_json_arr(self, jsonarr):
        
        for sat in jsonarr:
            if (sat.get('catnum', None) != None):
                catnum = int(sat.get('catnum'))
                if (catnum > 0 and catnum < 999999999 and not (catnum in self.__satlist.keys())):
                    freq = float(sat.get('freq', 0))
                    if (freq < 0):
                        #habria que avisar de esto
                        freq = abs(freq)
                    if (sat.get('script', None) != None):
                        script = os.path.abspath(sat['script'])
                        if (script != ""):
                            config_dict = {
                                "freq":freq,
                                "cmd":script,
                            }
                            self.__satlist[catnum] = config_dict


    def __parse_global_params_from_json_obj(self, jsonobj):
        
        if (jsonobj == None):
            raise RuntimeError("Error! Corrupted cfg file")

        lat = jsonobj.get('loc-lat', None)
        long = jsonobj.get('loc-long', None)
        elev = jsonobj.get('loc-elev', None)
        min_elev = jsonobj.get('min-elev', None)
        
        if (None in [lat, long, elev, min_elev]):
            raise RuntimeError("Error! Corrupted cfg file")
        
        self.loc_lat = float(lat)
        self.loc_long = float(long)
        self.loc_elev = int(elev)
        self.min_elev = int(min_elev)

    def __load_tles_to_mem(self):

        fetcher = SatTLEFetcher()
        db = CustomMemoryTLESource()

        sources = fetcher.fetch_urls()
        for file in sources:
            parsed = omm.parse_xml(file)
            fields = next(parsed, "")
            while (fields != ""):
                sat = Satrec()
                omm.initialize(sat, fields)
                db.add_tle(
                    sat.satnum, 
                    exporter.export_tle(sat), 
                    datetime_from_jday(sat.jdsatepoch, sat.jdsatepochF), 
                    fields.get('OBJECT_NAME', None)
                )
                fields = next(parsed, "")
        
        self.__tle_src_db = db

    def update_tle_db(self):
        self.__load_tles_to_mem()

    def get_tle_db(self) -> CustomMemoryTLESource:
        return self.__tle_src_db

    def get_tracked_list(self) -> dict[int,dict[str, str]]:
        return self.__satlist
    
    def get_location(self) -> Location:
        return Location('loc', self.loc_lat, self.loc_long, self.loc_elev)
    
    def get_minimal_elevation(self) -> int:
        return self.min_elev
    

            

