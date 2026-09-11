import os
import sys
import requests
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

WORKDIR = 'fetchs'
DEFAULT_SRC_FILENAME = 'tlesrc.json'
MAX_BYTESIZE = 8192
DEFAULT_SRC_OBJ = [{'name':'NOAA', 
                   'url':'https://celestrak.org/NORAD/elements/gp.php?GROUP=noaa&FORMAT=xml'}]
TIME_BETWEEN_UPDATES = timedelta(weeks=1)

class SatTLEFetcher():

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            logger.debug(f"[d] Entidad SatTLEFetcher no encontrada, creando entidad nueva.")
            cls.instance = super(SatTLEFetcher, cls).__new__(cls)
        return cls.instance

    def __init__(self, srcsfile=''):

        logger.debug(f"[d] Inicializando clase SatTLEFetcher con archivo de fuentes = {srcsfile}")
        self.__srcdb = []
        self.__workdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), WORKDIR)
        
        if (srcsfile != ''):
            logger.debug(f'[d] Cargando archivo de fuentes {srcsfile}')
            self.__srcsfile = os.path(srcsfile)
        else :
            logger.debug(f'[d] Archivo de fuentes no indicado, se carga el archivo por defecto = {DEFAULT_SRC_FILENAME} en la carpeta {self.__workdir}')
            self.__srcsfile = os.path.join(self.__workdir, DEFAULT_SRC_FILENAME)

        #check if srcfile & workdir exists
        if (not os.path.isdir(self.__workdir)):
            logger.debug(f'[d] No se encontró la carpeta {WORKDIR} en el directorio, creandola y un archivo por defecto.')
            os.mkdir(self.__workdir)

        if (not os.path.isfile(self.__srcsfile)):
            logger.debug(f'[d] No se encontró el archivo {self.__srcsfile}, generando uno por defecto con la configuración: {DEFAULT_SRC_OBJ}')
            with open(self.__srcsfile, 'w') as f:
                json.dump(DEFAULT_SRC_OBJ, f, indent=4)

        self.__srcdb = self.__parse_json_sources(self.__srcsfile)
                

    def __parse_json_sources(self, file) -> list[object]:
    
        srcs_obj = []
        seen = []

        with open(file, 'r', encoding='utf-8') as f:
            filebytes = f.read(MAX_BYTESIZE)
            doc = json.loads(filebytes)
            if type(doc) == list:
                for src in doc:
                    logger.debug(f'[d] Se leyó el registro: {src}')
                    if (src.get('name') != None and src.get('url')!=None and not src['name'] in seen):
                        if (src.get('timestamp') == None):
                            src['timestamp'] = 0
                        srcs_obj.append(src)
                        seen.append(src['name'])
                    elif src.get('name') != None or src.get('url') != None:
                        logger.warning(f'[w] El registro {src} no contiene al menos una de las dos claves necesarias para procesarlo, name o url.')
                    elif src['name'] in seen:
                        logger.warning(f'[w] El registro {src} está duplicado en el archivo.')
        
        return srcs_obj
    
    def __filename_from_srcname(self, srcname) -> str:
        return srcname + '.xml'
    
    def __filepath_from_srcname(self, srcname) -> os.path:
        return os.path.join(self.__workdir, self.__filename_from_srcname(srcname))
    
    def __verify_cached(self, src_obj) -> bool:
        filepath = self.__filepath_from_srcname(src_obj['name'])
        tstamp = src_obj['timestamp']
        if (os.path.isfile(filepath)):
            if (datetime.now() - datetime.fromtimestamp(tstamp) < TIME_BETWEEN_UPDATES):
                return True
        return False
    
    def fetch_urls(self) -> list[str]:
        #returns list of paths with resources to load.
        #caches sources in fetchs workdir
        
        srcfiles = []
        
        for src in self.__srcdb:
            if (not self.__verify_cached(src)):
                url = src['url']
                logger.debug(f'[d] Solicitando XML del url {url}.')
                try:
                    resp = requests.get(url, timeout=5)
                except requests.exceptions.Timeout:
                    #handle request timeout
                    logger.error(f'[E] La fuente {src['name']} falló por time out.')
                    print(f'''Source {src['name']} timed out''')
                    continue
                logger.debug(f'[d] Respuesta recibida de la fuente: {resp.text}')
                if (resp.status_code == 200):
                    filepath = self.__filepath_from_srcname(src['name'])
                    logger.debug(f'[d] Respuesta positiva, guardando resultado en {filepath}.')
                    with open(filepath, 'wb') as f:
                        f.write(resp.content)
                    src['timestamp'] = int(datetime.now().timestamp())
            srcfiles.append(self.__filepath_from_srcname(src['name']))

        with open(self.__srcsfile, 'w') as f:
            json.dump(self.__srcdb, f)
        
        return srcfiles

    def get_oldest_timestamp(self) -> datetime:
        now = datetime.now()
        oldest = now
        for src in self.__srcdb:
            timestamp = datetime.fromtimestamp(src.get('timestamp'))
            if timestamp == None:
                continue
            if timestamp < oldest:
                oldest = timestamp
        if oldest == now:
            oldest = datetime.min
        return oldest
