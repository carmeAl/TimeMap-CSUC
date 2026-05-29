import pandas as pd
import requests
import json
import re
from requests.auth import HTTPBasicAuth

# --- CONFIGURACIÓN ---
EXCEL_FILE = "Informacionclientes.xlsx"
SHEET_NAME = "Clients"
GRAFANA_URL = "http://localhost:3000"

# Credenciales Admin de Grafana
GRAFANA_USER = "tu_user_aqui"
GRAFANA_PASS = "tu_pass_aqui" 
auth_admin = HTTPBasicAuth(GRAFANA_USER, GRAFANA_PASS)

# InfluxDB Config
INFLUX_API_URL = "http://127.0.0.1:8086"       # Para que el script hable con Influx
INFLUX_GRAFANA_URL = "http://influxdb:8086"   # Para que Grafana hable con Influx (Docker)
INFLUX_ORG = "tu_org_aqui"
INFLUX_TOKEN_ADMIN = "tu_token_secreto_aqui"

INFINITY_HEALTH_URL = "http://172.17.0.1/ruta_al_archivo_latest_graph.json"
DASHBOARD_FILES = [
    "geomap-timemap.json",
    "geomap-timemap-node.json",
    "geomap-timemap-latency-jitter-details.json"
]

headers_base = {"Content-Type": "application/json"}
headers_i = {"Authorization": f"Token {INFLUX_TOKEN_ADMIN}", "Content-Type": "application/json"}

def get_influx_ids(bucket_name):
    try:
        res_orgs = requests.get(f"{INFLUX_API_URL}/api/v2/orgs", headers=headers_i).json()
        org_id = next((o['id'] for o in res_orgs['orgs'] if o['name'] == INFLUX_ORG), None)
        res_buck = requests.get(f"{INFLUX_API_URL}/api/v2/buckets?name={bucket_name}", headers=headers_i).json()
        bucket_id = res_buck['buckets'][0]['id'] if res_buck.get('buckets') else None
        return org_id, bucket_id
    except: return None, None

def create_scoped_token(org_id, bucket_id, cliente):
    payload = {
        "description": f"Token-Read-{cliente}",
        "orgID": org_id,
        "permissions": [{"action": "read", "resource": {"type": "buckets", "id": bucket_id, "orgID": org_id}}]
    }
    res = requests.post(f"{INFLUX_API_URL}/api/v2/authorizations", headers=headers_i, json=payload)
    return res.json().get('token') if res.status_code == 201 else None

def prepare_dashboard(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    
    # ASIGNACIÓN DE UIDS FIJOS
    # Esto asegura que los links entre dashboards no se rompan
    if "geomap-timemap-node.json" in file_path:
        data["uid"] = "geomap-timemap-node"
    elif "geomap-timemap-latency-jitter-details.json" in file_path:
        data["uid"] = "geomap-timemap-latency-jitter-details"
    elif "geomap-timemap.json" in file_path:
        data["uid"] = "geomap-timemap"

    # Preparación para la importación
    data["__inputs"] = [
        {"name": "DS_INFLUXDB", "label": "InfluxDB", "type": "datasource", "pluginId": "influxdb"},
        {"name": "DS_INFINITY", "label": "Infinity", "type": "datasource", "pluginId": "yesoreyeram-infinity-datasource"}
    ]
    data["id"] = None  # El ID numérico DEBE ser None para que Grafana cree uno nuevo
    return data

def set_home_dashboard(org_id, dashboard_uid):
    """Configura el dashboard indicado como Home para la organización actual"""
    headers = headers_base.copy()
    headers["X-Grafana-Org-Id"] = str(org_id)
    
    payload = {
        "homeDashboardUid": dashboard_uid
    }
    
    res = requests.put(f"{GRAFANA_URL}/api/org/preferences", auth=auth_admin, headers=headers, json=payload)
    
    if res.status_code == 200:
        print(f"    [OK] Home Dashboard fijado en: {dashboard_uid}")
    else:
        print(f"    [!] Error al fijar Home Dashboard: {res.text}")

def run_automation():
    # 1. Leer Clientes ajustando la cabecera a la fila 2 (A2)
    try:
        # skiprows=1 salta la fila A1. 
        # header=0 le dice que, tras saltar esa, la siguiente (A2) es la cabecera.
        df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME, usecols=[0], skiprows=1, header=0)
        
        # Nombre de la columna en A2
        col_name = df.columns[0].lower().strip()
        
        raw_list = df.iloc[:, 0].dropna().astype(str).str.strip()
        
        # Filtro de seguridad por si acaso
        prohibidos = [col_name, 'client', 'cliente', 'total', 'total_general','tu_organizacion_aqui']
        
        clientes = []
        for c in raw_list:
            c_clean = c.lower().replace(" ", "_").replace("@", "_")
            if c_clean in prohibidos or 'total' in c_clean:
                continue
            clientes.append(c_clean)
            
        clientes = list(set(clientes)) 
        print(f"[*] Clientes detectados para procesar: {clientes}")

    except Exception as e:
        print(f"Error Excel: {e}"); return

    import os
    print(f"Directori actual: {os.getcwd()}")
    print(f"Fitxers a la carpeta: {os.listdir('.')}")
   # 2. Preparar Dashboards
    dash_objs = []
    for f in DASHBOARD_FILES:
        # Usamos .strip() para eliminar cualquier espacio accidental
        f_clean = f.strip() 
        try:
            # Intentamos cargar el archivo limpio
            dash_objs.append(prepare_dashboard(f_clean))
            print(f"[OK] Archivo cargado correctamente: {f_clean}")
        except FileNotFoundError:
            print(f"[!] Saltando {f_clean}, no se encuentra. Revisa las comillas en el script.")
        except Exception as e:
            print(f"[!] Error con {f_clean}: {e}")
    for cli in clientes:
        print(f"\n>>> CONFIGURANDO: {cli.upper()}")

        # A. Organización
        requests.post(f"{GRAFANA_URL}/api/orgs", auth=auth_admin, json={"name": cli})
        res_find = requests.get(f"{GRAFANA_URL}/api/orgs/name/{cli}", auth=auth_admin)
        if res_find.status_code != 200: continue
        
        org_id = res_find.json().get('id')
        h_org = headers_base.copy()
        h_org["X-Grafana-Org-Id"] = str(org_id)

        # B. Data Source InfluxDB
        i_org, i_buck = get_influx_ids(cli)
        if i_buck:
            token = create_scoped_token(i_org, i_buck, cli)
            if token:
                ds_i = {
                    "name": f"InfluxDB_{cli}",
                    "type": "influxdb",
                    "access": "proxy",
                    "url": INFLUX_GRAFANA_URL,
                    "jsonData": {"version": "Flux", "organization": INFLUX_ORG, "defaultBucket": cli},
                    "secureJsonData": {"token": token}
                }
                requests.post(f"{GRAFANA_URL}/api/datasources", auth=auth_admin, headers=h_org, json=ds_i)

        # C. Data Source Infinity
        ds_inf = {
            "name": "Infinity_Data",
            "type": "yesoreyeram-infinity-datasource",
            "access": "proxy",
            "jsonData": {
                "healthCheckEnabled": True,
                "healthCheckUrl": INFINITY_HEALTH_URL
            }
        }
        requests.post(f"{GRAFANA_URL}/api/datasources", auth=auth_admin, headers=h_org, json=ds_inf)

        # D. Importar Dashboards
        for d in dash_objs:
            payload = {
                "dashboard": d, "overwrite": True,
                "inputs": [
                    {"name": "DS_INFLUXDB", "type": "datasource", "pluginId": "influxdb", "value": f"InfluxDB_{cli}"},
                    {"name": "DS_INFINITY", "type": "datasource", "pluginId": "yesoreyeram-infinity-datasource", "value": "Infinity_Data"}
                ]
            }
            requests.post(f"{GRAFANA_URL}/api/dashboards/import", auth=auth_admin, headers=h_org, json=payload)
            # Llamamos a la función después de asegurar que los dashboards ya existen en la org
            set_home_dashboard(org_id, "geomap-timemap")
        print(f"    [OK] Configuración completada para {cli}")

if __name__ == "__main__":
    run_automation()

