import json
from typing import List, Dict
from abc import ABC, abstractmethod
from custom_classes import CustomOverpass
import threading
import uvicorn
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

class PassRepository:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(PassRepository, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, ARGS):
        if not hasattr(self, "_initialized"):  # evita re-inicializar
            self._initialized = True
            self._passes: List[CustomOverpass] = []
            self._observers = []

            #Registrar Observadores
            if ARGS.PASSES_OUTFILE: self._observers.append(FilePassesObserver(self, filename=ARGS.PASSES_OUTFILE))

            #Inicializar Servicios
            if ARGS.API: PassesApiService(self, port=ARGS.API[0], host=ARGS.API[1])

    def update_passes(self, new_passes: List[CustomOverpass]):
        """Actualiza la lista y notifica automáticamente."""
        self._passes = new_passes
        self.notify_observers()

    def notify_observers(self):
        for obs in self._observers:
            obs.update()

    @property
    def passes(self):
        return self._passes


class BasePassesObserver(ABC):
    def __init__(self, repository: PassRepository):
        self._repo = repository

    @abstractmethod
    def update(self):
        """Cada observer implementa su propia lógica"""
        pass


class FilePassesObserver(BasePassesObserver):
    def __init__(self, repository: PassRepository, filename):
        super().__init__(repository)
        self.filename = filename
        logger.info(f"[FilePassesExport] Inicializado para escribir en {self.filename}")

    def update(self):
        data = [p.to_dict() for p in self._repo.passes]
        try:
            with open(self.filename, "w") as f:
                json.dump(data, f, indent=4)
            logger.debug(f"[FilePassesExport] Archivo actualizado, {len(self._repo.passes)} pasadas guardadas en {self.filename}")
        except (OSError, IOError) as e:
            logger.error(f"[FilePassesExport] Error al escribir en {self.filename}: {e}")


class PassesApiService():
    def __init__(self, repository: PassRepository, port, host):
        self._repo = repository
        self._host = host
        self._port = port
        
        # Crear la app FastAPI
        self.app = FastAPI()

        @self.app.get("/passes")
        def get_passes():
            return [p.to_dict() for p in self._repo.passes]

        @self.app.get("/next")
        def get_next_pass():
            return self._repo.passes[0].to_dict() if self._repo.passes else {}

        @self.app.get("/passes/{sat_id}")
        def get_passes_by_id(sat_id: int):
            return [p.to_dict() for p in self._repo.passes if p.sate_id == sat_id]

        # Lanzar uvicorn en un hilo separado
        thread = threading.Thread(
            target=uvicorn.run,
            args=(self.app,),
            kwargs={"host": self._host, "port": self._port, "log_level": "warning"},
            daemon=True
        )
        thread.start()

        logger.info(f"[API] API corriendo en {self._host}:{self._port}")
