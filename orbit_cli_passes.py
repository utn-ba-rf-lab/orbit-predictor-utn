import sys
import json
from pathlib import Path
from datetime import datetime

MSNL=20 #MAX_SAT_NAME_LENGTH

delete_chars = " _-."   # caracteres a eliminar: espacio, guion bajo, guión medio y punto
delete_table = str.maketrans("", "", delete_chars) # tabla de traduccion


def format_time(iso_str):
    # Convierte la cadena ISO a objeto datetime
    dt = datetime.fromisoformat(iso_str)
    # Devuelve la fecha formateada, solo fecha y hora sin microsegundos ni zona
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def mostrar_pasadas(json_file, sat_filter=None):
    json_file_path = Path(json_file)
    
    try:
        with open(json_file_path) as f:
            passes = json.load(f)
    except FileNotFoundError:
        print(f"No se encontró el archivo de pasadas en {json_file_path}")
        return
    except PermissionError:
        print(f"Permisos de lectura denegados para {json_file_path}")
        return
    except Exception as e:
        print(f"Error al leer {json_file_path}: {e}")
        return
    
    for p in passes:
        if sat_filter and not (
            str(p["sat_id"]) == str(sat_filter) or 
            str(p["sat_name"]) == str(sat_filter) or 
            str(p["sat_name"]).lower().translate(delete_table) == str(sat_filter).lower().translate(delete_table)
            ):
            continue
        print(
            f"Satélite: {p['sat_name'][:(MSNL-3)]+'...' if len(p['sat_name'])>MSNL else p['sat_name']:<{MSNL}} | "
            f"CatNum: {p['sat_id']} | "
            f"AOS: {format_time(p['aos'])} | "
            f"LOS: {format_time(p['los'])} | "
            f"Elevación máxima: {p['elev_max']}"
        )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: orbit_cli.py <archivo_json> [satélite]")
    else:
        json_file = sys.argv[1]
        #Validar el segundo arguemnto (que es opcional): se utiliza para mostrar las pasadas de un solo satélite
        sat_filter = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None
        mostrar_pasadas(json_file, sat_filter)
