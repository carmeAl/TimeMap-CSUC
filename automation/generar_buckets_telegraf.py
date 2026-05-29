import pandas as pd
from influxdb_client import InfluxDBClient
import re
import os
import subprocess

# --- CONFIGURACIÓN ---
EXCEL_FILE = "tu_excel_aqui"
SHEET_NAME = "Clients"
CONF_FILE = "/etc/telegraf/telegraf.conf"
INFLUX_URL = "http://127.0.0.1:8086"
INFLUX_TOKEN = "tu_token_secreto_aqui"
INFLUX_ORG = "tu_organizacion_aqui"

def update_infrastructure():
    # 1. Obtener clientes del Excel
    try:
        df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, usecols=[0], skiprows=1, header=0)
        clientes_raw = df.iloc[:, 0].dropna().astype(str).str.strip()
        # Filtramos el total y nombres raros
        lista_clientes = [c.lower().replace(" ", "_").replace("@", "_") for c in clientes_raw if "Total general" not in c]
        lista_clientes = list(set(lista_clientes)) # Quitar duplicados
    except Exception as e:
        print(f"[!] Error leyendo el Excel: {e}")
        return

    # 2. Crear Buckets en InfluxDB
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    buckets_api = client.buckets_api()
    
    for bucket_name in lista_clientes:
        try:
            if not buckets_api.find_bucket_by_name(bucket_name):
                buckets_api.create_bucket(bucket_name=bucket_name, org=INFLUX_ORG)
                print(f"[+] Bucket creado: {bucket_name}")
        except Exception as e:
            print(f"[!] Error creando bucket {bucket_name}: {e}")

    # 3. Generar el bloque de texto para Telegraf
    nuevo_bloque_outputs = "\n"
    for cliente in lista_clientes:
        nuevo_bloque_outputs += f
        """[[outputs.influxdb_v2]]
  urls = ["{INFLUX_URL}"]
  token = "{INFLUX_TOKEN}"
  organization = "{INFLUX_ORG}"
  bucket = "{cliente}"
  [outputs.influxdb_v2.tagpass]
    cliente = ["{cliente}"] """

    # 4. Inyectar en telegraf.conf usando los marcadores
    try:
        with open(CONF_FILE, "r") as f:
            contenido = f.read()

        pattern = r"# --- INICIO CLIENTES DINAMICOS ---.*?# --- FIN CLIENTES DINAMICOS ---"
        replacement = f"# --- INICIO CLIENTES DINAMICOS ---{nuevo_bloque_outputs}# --- FIN CLIENTES DINAMICOS ---"
        
        nuevo_contenido = re.sub(pattern, replacement, contenido, flags=re.DOTALL)

        with open(CONF_FILE, "w") as f:
            f.write(nuevo_contenido)
        
        print(f"[OK] {len(lista_clientes)} clientes configurados en {CONF_FILE}")

    except PermissionError:
        print(f"[!] Error de permisos: No se pudo escribir en {CONF_FILE}. Intenta con sudo -E.")
    except Exception as e:
        print(f"[!] Error al actualizar la configuración: {e}")

    client.close()

    # 5. REINICIAR TELEGRAF
    print("[*] Reiniciando el servicio Telegraf...")
    try:
        subprocess.run(["sudo", "systemctl", "restart", "telegraf"], check=True)
        print("[OK] Telegraf se ha reiniciado correctamente.")
    except Exception as e:
        print(f"[!] No se pudo reiniciar Telegraf automáticamente: {e}")
        print("[i] Prueba a reiniciarlo manualmente: sudo systemctl restart telegraf")

if __name__ == "__main__":
    update_infrastructure()

