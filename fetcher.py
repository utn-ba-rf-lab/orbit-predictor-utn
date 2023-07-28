import os
import sys
import requests
import json
from datetime import datetime, timedelta

WORKDIR = 'fetchs'
DEFAULT_SRC_FILENAME = 'tlesrc.json'
MAX_BYTESIZE = 8192
DEFAULT_SRC_OBJ = [{'name':'NOAA', 
                   'url':'https://celestrak.org/NORAD/elements/gp.php?GROUP=noaa&FORMAT=xml'}]

class SatTLEFetcher():

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(SatTLEFetcher, cls).__new__(cls)
        return cls.instance

    def __init__(self, srcsfile=''):

        self.__srcdb = []
        self.__workdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), WORKDIR)
        
        if (srcsfile != ''):
            self.__srcsfile = os.path(srcsfile)
        else :
            self.__srcsfile = os.path.join(self.__workdir, DEFAULT_SRC_FILENAME)

        #check if srcfile & workdir exists
        if (not os.path.isdir(self.__workdir)):
            os.mkdir(self.__workdir)

        if (not os.path.isfile(self.__srcsfile)):
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
                    if (src.get('name') != None and src.get('url')!=None and not src['name'] in seen):
                        if (src.get('timestamp') == None):
                            src['timestamp'] = 0
                        srcs_obj.append(src)
                        seen.append(src['name'])
        
        return srcs_obj
    
    def __filename_from_srcname(self, srcname) -> str:
        return srcname + '.xml'
    
    def __filepath_from_srcname(self, srcname) -> os.path:
        return os.path.join(self.__workdir, self.__filename_from_srcname(srcname))
    
    def __verify_cached(self, src_obj) -> bool:
        filepath = self.__filepath_from_srcname(src_obj['name'])
        tstamp = src_obj['timestamp']
        if (os.path.isfile(filepath)):
            if (datetime.now() - datetime.fromtimestamp(tstamp) < timedelta(weeks=1)):
                return True
        return False
    
    def fetch_urls(self) -> list[str]:
        #returns list of paths with resources to load.
        #caches sources in fetchs workdir
        
        srcfiles = []
        
        for src in self.__srcdb:
            if (not self.__verify_cached(src)):
                url = src['url']
                try:
                    resp = requests.get(url, timeout=5)
                except requests.exceptions.Timeout:
                    #handle request timeout
                    print(f'''Source {src['name']} timed out''')
                    continue
                if (resp.status_code == 200):
                    filepath = self.__filepath_from_srcname(src['name'])
                    with open(filepath, 'wb') as f:
                        f.write(resp.content)
                    src['timestamp'] = int(datetime.now().timestamp())
            srcfiles.append(self.__filepath_from_srcname(src['name']))

        with open(self.__srcsfile, 'w') as f:
            json.dump(self.__srcdb, f)
        
        return srcfiles



        



                
