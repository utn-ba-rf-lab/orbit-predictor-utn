import re
import datetime as dt

MSNL=15 #MAX_SATE_NAME_LENGTH


def format_len_text(texto, max_len):
    if len(texto)>max_len:  
        return texto[:(max_len-3)]+'...' 
    return f"{texto:<{max_len}}"

def format_sate_name(nombre_satelite):
    return format_len_text(nombre_satelite, MSNL)


DELETE_CHARS = " -._\"'´`"
DELETE_TABLE = str.maketrans("", "", DELETE_CHARS)

def normalizar_sate_name(sate_name: str) -> str:
    return sate_name.lower().translate(DELETE_TABLE)

def build_filtro(filtro: str):
    filtro = normalizar_sate_name(filtro)
    patron = ("^" + re.escape(filtro).replace(r"\*", ".*") + "$")
    return re.compile(patron)

def sate_name_matches(sate_name, patron):
    sate_name = normalizar_sate_name(sate_name)
    return patron.match(sate_name)

def format_fecha_utc(fecha):
    if fecha is None:
        return None

    if not isinstance(fecha, dt.datetime):
        return None
    
    return fecha.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + " UTC"
