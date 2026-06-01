import requests
from requests.auth import HTTPBasicAuth

# --- CONFIGURACIÓN ---
GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = "tu_usuario_admin_grafana_aqui"
GRAFANA_PASS = "tu_contraseña_admin_grafana_aqui"
auth_admin = HTTPBasicAuth(GRAFANA_USER, GRAFANA_PASS)

INFLUX_API_URL = "http://127.0.0.1:8086"
INFLUX_TOKEN_ADMIN = "tu_token_secreto_con_todos_permisos_aqui"
headers_i = {"Authorization": f"Token {INFLUX_TOKEN_ADMIN}", "Content-Type": "application/json"}

def cleanup():
    print("--- INICIANDO LIMPIEZA DE ENTORNO ---")

    # 1. ELIMINAR ORGANIZACIONES EN GRAFANA
    print("\n[*] Eliminando organizaciones en Grafana...")
    res_orgs = requests.get(f"{GRAFANA_URL}/api/orgs", auth=auth_admin)
    
    if res_orgs.status_code == 200:
        orgs = res_orgs.json()
        for org in orgs:
            org_id = org['id']
            org_name = org['name']
            
            # PROTECCIÓN: No eliminar la organización principal (ID 1)
            if org_id == 1:
                print(f"    [-] Saltando {org_name} (ID 1 - Org Principal)")
                continue
            
            res_del = requests.delete(f"{GRAFANA_URL}/api/orgs/{org_id}", auth=auth_admin)
            if res_del.status_code == 200:
                print(f"    [OK] Organización '{org_name}' eliminada.")
            else:
                print(f"    [X] Error eliminando '{org_name}': {res_del.text}")
    else:
        print(f"[!] No se pudo obtener la lista de organizaciones: {res_orgs.text}")

    # 2. ELIMINAR TOKENS EN INFLUXDB
    print("\n[*] Eliminando tokens residuales en InfluxDB...")
    res_auths = requests.get(f"{INFLUX_API_URL}/api/v2/authorizations", headers=headers_i)
    
    if res_auths.status_code == 200:
        auths = res_auths.json().get('authorizations', [])
        count = 0
        for auth in auths:
            desc = auth.get('description', '')
            auth_id = auth['id']
            
            # Filtramos por la descripción que pusimos en los otros scripts
            if "Grafana" in desc or "Token-" in desc or "ReadOnly" in desc:
                res_del_auth = requests.delete(f"{INFLUX_API_URL}/api/v2/authorizations/{auth_id}", headers=headers_i)
                if res_del_auth.status_code == 204:
                    print(f"    [OK] Token eliminado: {desc}")
                    count += 1
        if count == 0:
            print("    [-] No se encontraron tokens para eliminar.")
    else:
        print(f"[!] No se pudo obtener la lista de tokens: {res_auths.text}")

    print("\n--- LIMPIEZA FINALIZADA ---")

if __name__ == "__main__":
    confirm = input("¿Estás seguro de que quieres borrar TODAS las organizaciones (excepto la ID 1)? (s/n): ")
    if confirm.lower() == 's':
        cleanup()
    else:
        print("Operación cancelada.")

