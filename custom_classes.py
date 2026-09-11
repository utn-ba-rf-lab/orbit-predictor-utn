import datetime as dt
import math

class CustomPredictor():
    def __init__(self, predictor):
        self._predictor = predictor
        self._custom_next_pass_date = dt.datetime.now(tz=dt.timezone.utc)

    def __getattr__(self, attr_name):
        # Se buscan los metodos/atributos que no esten en esta clase en la clase original.
        if '_predictor' not in self.__dict__:
             raise AttributeError(f"{attr_name} No encontrado")
        return getattr(self._predictor, attr_name)

    @property
    def custom_next_pass_date(self):
        return self._custom_next_pass_date
    
    @custom_next_pass_date.setter
    def custom_next_pass_date(self, value):
        self._custom_next_pass_date = value
    
    @property
    def predictor(self):
        return self._predictor
    
    @predictor.setter
    def predictor(self, value):
        self._predictor = value

    def orbit_number_at(self, aos_overpass):
        """
        Calcula el número de órbita en el instante dado (AOS).
        Usa el rev_number del TLE y el período orbital.
        
        Args:
            aos_overpass (datetime): Momento del AOS en UTC.

        Returns:
            int: Número de órbita correspondiente al instante.
        """

        #Período del satélite en minutos
        _orbit_period = 2*math.pi /self._predictor.mean_motion      

        #A partir de la segunda línea del tle se consigue el número de orbita (número de revolución) en la época del TLE 
        _rev_number_tle =int(self._predictor.tle.lines[1][63:68])   # columnas 64–68
        
        #Momento en el que fue generado el TLE
        _epoch_tle = self._predictor.tle.date.replace(tzinfo=dt.timezone.utc)

        _delta_minutes = (aos_overpass - _epoch_tle).total_seconds() / 60

        _orbits_since_epoch = math.floor(_delta_minutes / _orbit_period)

        _orbit_number = _rev_number_tle + _orbits_since_epoch

        return _orbit_number


class CustomOverpass():
    def __init__(self, pasada, predictor):
        self._overpass = pasada
        self._predictor = predictor
        self._task = None      
        self._overlapped_passes=[]
        self._orbit_number = self._predictor.orbit_number_at(self._overpass.aos)

    def __getattr__(self, attr_name):
        # Se buscan los metodos/atributos que no esten en esta clase en la clase original.
        if '_overpass' not in self.__dict__:
             raise AttributeError(f"{attr_name} No encontrado")
        return getattr(self._overpass, attr_name)

    def discard_due_to_overlap(self):
        self._verify_overlapped_passes()
        self._cancel_task()

    def _cancel_task(self):
        if self.task is not None:
            self._task.cancel()
            self._task = None

    def prefer_over(self, discarded_pass):
        #Se conserva la referencia a la pasada descartada
        self._overlapped_passes.append(discarded_pass)
        discarded_pass.discard_due_to_overlap()

    def _verify_overlapped_passes(self):
        now = dt.datetime.now(dt.timezone.utc)
        self._overlapped_passes = [e for e in self._overlapped_passes if e.aos > now]

    def handle_candidate_pass(self):
        #La pasada tiene referenciado el predictor del satelite. Se actualiza el punto de busqueda del predictor con el LOS de la pasada que se va a considerar.
        self._predictor.custom_next_pass_date=self.los

    def to_dict(self):
        return {
            "satelite": self.sate_id,
            "aos": self.aos.isoformat() if hasattr(self.aos, "isoformat") else self.aos,
            "los": self.los.isoformat() if hasattr(self.los, "isoformat") else self.los,
            "elev_max": f"{self.max_elevation_deg:.1f}°",
        }

    @property
    def overlapped_passes(self):
        now = dt.datetime.now(dt.timezone.utc)
        # Se filtra y actualiza la lista
        self._verify_overlapped_passes()
        # Se devulve una copia de la lista 
        return self._overlapped_passes[:]

    def recover_overlapped_passes(self):
        rec_list=self.overlapped_passes
        self._overlapped_passes = []
        return rec_list

    @property
    def task(self):
        return self._task
    
    @task.setter
    def task(self, value):
        self._task = value

    @property
    def predictor(self):
        return self._predictor

    @property
    def orbit_number(self):
        return self._orbit_number
