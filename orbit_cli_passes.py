import sys
import json
from pathlib import Path
from datetime import datetime

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
        if sat_filter and str(p["satelite"]) != str(sat_filter):
            continue
        print(
            f"Satélite: {p['satelite']} | "
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
        sat_filter = sys.argv[2] if len(sys.argv) > 2 else None
        mostrar_pasadas(json_file, sat_filter)
