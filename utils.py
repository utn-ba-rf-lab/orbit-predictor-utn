

MSNL=15 #MAX_SATE_NAME_LENGTH


def format_len_text(texto, max_len):
    if len(texto)>max_len:  
        return texto[:(max_len-3)]+'...' 
    return f"{texto:<{max_len}}"

def format_sate_name(nombre_satelite):
    return format_len_text(nombre_satelite, MSNL)
