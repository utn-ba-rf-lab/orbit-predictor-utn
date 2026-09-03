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
import logging

logger = logging.getLogger(__name__)

DEFAULT_CFG_FILENAME = 'cfg.json'

## NOAA 19
DEFAULT_CFG_OBJ = {'global-params':{'min-elev': 40, 'loc-lat':0, 'loc-long':0, 'loc-elev':0},
                   'tracked-sats':[{'catnum':'33591',
                                    'script':'',
                                    'priority':'0'}]
                    }
MAX_BYTESIZE = 8192

class CustomMemoryTLESource(TLESource):

    def __init__(self):
        self.__db = defaultdict(dict)

    def add_tle(self, sate_id, tle, epoch, alias=None):
        if (alias != None):
            self.__db[sate_id]['alias'] = alias
        elif (self.__db[sate_id].get('alias', None) == None):  
            self.__db[sate_id]['alias'] = ""

        if (self.__db[sate_id].get('tles', None) == None):
            self.__db[sate_id]['tles'] = set()
        
        self.__db[sate_id]['tles'].add((epoch, tle))

    def _get_tle(self, sate_id, date):
        if (self.__db[sate_id].get('tles') is None):
            raise LookupError(f'Missing tle data for CATID #{sate_id}, check configured sources.')
        
        candidates = self.__db[sate_id]['tles']
        winner = None
        winner_dt = float("inf")

        for epoch, candidate in candidates:
            c_dt = abs((epoch - date).total_seconds())
            if c_dt < winner_dt:
                winner = candidate
                winner_dt = c_dt

        if winner is None:
            raise LookupError("No tles in storage")

        return winner
    
    def get_name_from_id(self, sate_id) -> str:
        if (self.__db.get(sate_id, None) != None):
            return self.__db[sate_id].get('alias', "")
        return ""

class SatTrackCfg():

    def __init__(self, id:int, script_path:str, priority:int):
        logger.debug(f"[d] Inicializando clase SatTrackCFG con id = {id}, script_path = {script_path}, y priority = {priority}")
        self.__id = id
        self.__script_path = script_path
        self.__priority = priority

    def get_id(self) -> int:
        return self.__id
    
    def get_script(self) -> os.path:
        return os.path.abspath(os.path.expanduser(self.__script_path))
    
    def get_priority(self) -> int:
        return self.__priority

class SatLoader():
    
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            logger.debug(f"[d] Entidad SatLoader no encontrada, creando entidad nueva.")
            cls.instance = super(SatLoader, cls).__new__(cls)
        return cls.instance
    
    def __init__(self, cfgfile=''):
        logger.debug(f"[d] Inicializando SatLoader.")
        self.__satlist = {}

        logger.debug(f"[d] Cargando archivo .cfg.")
        if (cfgfile != '' and os.path.isfile(os.path.abspath(cfgfile))):
            logger.debug(f"[d] Se especificó un archivo .cfg no predeterminado y se encontró, cargándolo.")
            self.__cfgfile = os.path.abspath(cfgfile)
        elif (cfgfile != ''):
            logger.warning(f"[w] Se especificó un archivo .cfg no predeterminado pero no se encontró el archivo. Creando un archivo con la configuración por defecto.")
            self.__cfgfile = os.path.dirname(os.path.abspath(cfgfile))
            if not (os.path.isfile(self.__cfgfile)):
                with open(self.__cfgfile, 'w') as f:
                    json.dump(DEFAULT_CFG_OBJ, f, indent=4)
        else:
            script_path = os.path.dirname(os.path.abspath(__file__))
            self.__cfgfile = os.path.join(script_path, DEFAULT_CFG_FILENAME)
            if not (os.path.isfile(self.__cfgfile)):
                with open(self.__cfgfile, 'w') as f:
                    json.dump(DEFAULT_CFG_OBJ, f, indent=4)
            logger.warning(f"[w] No se especificó un archivo .cfg, se utilizará el que se encuentre en {self.__cfgfile}.")

        with open(self.__cfgfile, 'r', encoding='utf-8') as f:
            contents = f.read(MAX_BYTESIZE)
            cfg = json.loads(contents)
            logger.debug(f'[d] Se leyó del archivo lo siguiente: ')
            logger.debug(f'    {cfg}')
        
        if (type(cfg) != dict):
            logger.error(f'[E] La entidad cargada no es un objeto JSON.')
            raise RuntimeError("Error! Root config entity is not a json object")
        
        self.__parse_global_params_from_json_obj(cfg.get('global-params', None))
        self.__parse_satlist_from_json_arr(cfg.get('tracked-sats', []))
        self.__load_tles_to_mem()
            

    def __parse_satlist_from_json_arr(self, jsonarr):
        for sat in jsonarr:
            if (sat.get('catnum', None) == None): 
                logger.error(f"[E] Satélite sin número de catalogo."); continue
            catnum = int(sat.get('catnum'))
            if (catnum < 0 or catnum > 999999999): 
                logger.error(f"[E] Número de catalogo erroneo: {catnum}"); continue
            if (catnum in self.__satlist.keys()): 
                logger.error(f"[E] Número de catalogo repetido: {catnum}"); continue
            if (sat.get('script', None) == None): 
                logger.error(f"[E] Satélite sin script asociado."); continue
            script = sat['script']
            if (script == ""): 
                logger.error(f"[E] Script de satélite vacío."); continue

            if (sat.get('priority', None) == None): 
                logger.error(f"[E] Satélite sin número de prioridad."); continue
            priority = int(sat.get('priority'))
            if (priority < 0): 
                logger.error(f"[E] Número de prioridad negativo para satélite: {catnum}"); continue
            
            self.__satlist[catnum] = SatTrackCfg(catnum, script, priority)


    def __parse_global_params_from_json_obj(self, jsonobj):
        if (jsonobj == None):
            logger.error(f'[E] No se cargó correctamente el archivo cfg.')
            raise RuntimeError("Error! Corrupted cfg file")

        lat = jsonobj.get('loc-lat', None)
        if (lat == None): 
            logger.error(f'[E] No se cargó la latitud del lugar.')
 
        long = jsonobj.get('loc-long', None)
        if (long == None): 
            logger.error(f'[E] No se cargó la longitud del lugar.')
 
        elev = jsonobj.get('loc-elev', None)
        if (elev == None): 
            logger.error(f'[E] No se cargó la elevación del lugar.')
 
        min_elev = jsonobj.get('min-elev', None)
        if (min_elev == None): 
            logger.error(f'[E] No se cargó la elevación mínima esperada.')
        
        if (None in [lat, long, elev, min_elev]):
            logger.error(f'[E] No se encontraron campos necesarios para la ejecución del programa.')
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
            logger.debug(f'[d] Cargando archivo {file}')
            parsed = omm.parse_xml(file)
            for count, fields in enumerate(parsed):
                if count < 25: 
                    logger.debug(f'[d] Se leyó el registro: {fields}')
                elif count == 25:
                    logger.debug(f'[d] Se leyeron los primeros 25 registros, quedan registros a leer que no se van a imprimir.') 
                sat = Satrec()
                omm.initialize(sat, fields)
                db.add_tle(
                    sat.satnum, 
                    exporter.export_tle(sat), 
                    datetime_from_jday(sat.jdsatepoch, sat.jdsatepochF), 
                    fields.get('OBJECT_NAME', None)
                )
            logger.debug(f'[d] Se leyeron {count} registros, de los que se imprimieron en pantalla los primeros 25.')
        
        self.__tle_src_db = db

    def reload_tle_db(self):
        self.__load_tles_to_mem()

    def get_tle_db(self) -> CustomMemoryTLESource:
        return self.__tle_src_db

    def get_tracked_list(self) -> dict[int,SatTrackCfg]:
        return self.__satlist
    
    def get_location(self) -> Location:
        return Location('loc', self.loc_lat, self.loc_long, self.loc_elev)
    
    def get_last_update_timestamp(self) -> Datetime:
        fetcher = SatTLEFetcher()
        timestamp = fetcher.get_oldest_timestamp()
        return timestamp

