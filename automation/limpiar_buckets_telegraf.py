import pandas as pd
from influxdb_client import InfluxDBClient
import re
import os

# --- CONFIGURACIÓN (Misma que el anterior) ---
EXCEL_FILE = "Tu_Nombre_fichero_excel_aqui_.xlsx"
SHEET_NAME = "Clients"
CONF_FILE = "/etc/telegraf/telegraf.conf"
INFLUX_URL = "http://127.0.0.1:8086"
INFLUX_TOKEN = "tu_token_secreto_aqui"
INFLUX_ORG = "tu_organizacion_aqui"

def limpiar_todo():
    # 1. Obtener clientes del Excel para saber qué borrar
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, usecols=[0])
        clientes_raw = df.iloc[:, 0].dropna().astype(str).str.strip()
        lista_clientes = [c.lower().replace(" ", "_").replace("@", "_") for c in clientes_raw if "Total general" not in c]
        lista_clientes = list(set(lista_clientes))
    except Exception as e:
        print(f"[!] Error leyendo Excel: {e}")
        return

    # 2. Borrar Buckets en InfluxDB
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    buckets_api = client.buckets_api()
    
    print("[*] Iniciando borrado de buckets...")
    for bucket_name in lista_clientes:
        bucket = buckets_api.find_bucket_by_name(bucket_name)
        if bucket:
            buckets_api.delete_bucket(bucket.id)
            print(f"[-] Bucket eliminado: {bucket_name}")
        else:
            print(f"[.] El bucket {bucket_name} no existe, nada que hacer.")

    # 3. Limpiar telegraf.conf (Vaciar lo que hay entre marcadores)
    try:
        with open(CONF_FILE, "r") as f:
            contenido = f.read()

        # El patrón busca todo lo que haya entre los dos comentarios y lo deja vacío
        pattern = r"(# --- INICIO CLIENTES DINAMICOS ---).*?(# --- FIN CLIENTES DINAMICOS ---)"
        replacement = r"\1\n\2" # Mantiene los marcadores pero quita el contenido
        
        nuevo_contenido = re.sub(pattern, replacement, contenido, flags=re.DOTALL)

        with open(CONF_FILE, "w") as f:
            f.write(nuevo_contenido)
        print(f"[OK] Archivo {CONF_FILE} limpiado.")
    except PermissionError:
        print("[!] Error: No tienes permisos para modificar telegraf.conf (usa sudo -E)")
    except Exception as e:
        print(f"[!] Error al limpiar config: {e}")

    client.close()

if __name__ == "__main__":
    confirmacion = input("¿Estás seguro de que quieres BORRAR todos los buckets y la config de Telegraf? (s/n): ")
    if confirmacion.lower() == 's':
        limpiar_todo()
    else:
        print("Operación cancelada.")

