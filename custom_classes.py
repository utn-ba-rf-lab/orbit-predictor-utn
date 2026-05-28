import datetime as dt


class CustomPredictor():
    def __init__(self, predictor):
        self._predictor = predictor
        print(type(predictor))
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


class CustomOverpass():
    def __init__(self, pasada, predictor):
        self._overpass = pasada
        self._predictor = predictor
        self._task = None      
        self._overlapped_passes=[]
        

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

    @property
    def overlapped_passes(self):
        now = dt.datetime.now(dt.timezone.utc)
        # Se filtra y actualiza la lista
        self._verify_overlapped_passes()
        # Se devulve una copia de la lista 
        return self._overlapped_passes[:]

    @property
    def task(self):
        return self._task
    
    @task.setter
    def task(self, value):
        self._task = value

    @property
    def task(self):
        return self._task
    
    @task.setter
    def task(self, value):
        self._task = value

    @property
    def predictor(self):
        return self._predictor
    
    @predictor.setter
    def predictor(self, value):
        self._predictor = value
