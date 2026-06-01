#! /usr/bin/python3

import os, sys, re, subprocess, json

# --- TABLA DE UBICACIONES Y CLIENTES CSUC ---
CSUC_LOCATIONS = {
    "lapica": {"latitude": aqui_la_latitude , "longitude": la_longitude_aqui},
    "pedraforca": {"latitude": aqui_la_latitude, "longitude": la_longitude_aqui},
    "uab": {"latitude": aqui_la_latitude, "longitude": la_longitude_aqui},
    "uab-cs": {"latitude": aqui_la_latitude, "longitude": la_longitude_aqui},
    "uab-r": {"latitude": aqui_la_latitude, "longitude": la_longitude_aqui},
    "uao": {"latitude": aqui_la_latitude, "longitude": la_longitude_aqui},
    "ub": {"latitude": aqui_la_latitude, "longitude": la_longitude_aqui},
    "ub-ff": {"latitude": aqui_la_latitude, "longitude": la_longitude_aqui},
    "udg": {"latitude": aqui_la_latitude, "longitude": la_longitude_aqui},
    "udg-parcudg": {"latitude": aqui_la_latitude, "longitude": la_longitude_aqui},
}

SERVER_IP = "10.0.0.13"

def get_node_by_ip(ip):
    for name, info in CSUC_LOCATIONS.items():
        if info["ip"] == ip:
            return {"name": name, **info}
    return {"name": ip, "lat": 0.0, "lon": 0.0, "group": "unknown"}

def parse_twping(raw_output):
    data = {}
    rtt_pattern = r'round-trip time min/median/max\s+=\s+[\d\.]+/(?P<median>\d+\.?\d*)/[\d\.]+'
    jit_pattern = r'two-way jitter\s+=\s+(?P<jitter>\d+\.?\d*)'
    m_rtt = re.search(rtt_pattern, raw_output)
    m_jit = re.search(jit_pattern, raw_output)
    if m_rtt: data['avg'] = float(m_rtt.group('median'))
    if m_jit: data['jitter'] = float(m_jit.group('jitter'))
    return data

def run_twping(dip):
    # -Z para ignorar problemas de NTP
    cmd = ["/usr/bin/twping", "-c", "5", "-Z", "-L", "0.5", "-S", SERVER_IP, dip]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        return parse_twping(result.stdout)
    except:
        return {}

def main():
    if len(sys.argv) < 3:
        return json.dumps({"error": "Faltan argumentos"})
    
    hub_ip = sys.argv[1]
    dst_ip = sys.argv[2]

    res_hub = run_twping(hub_ip)
    res_dst = run_twping(dst_ip)

    if 'avg' in res_hub and 'avg' in res_dst:
        rtt_diff = max(0.1, res_dst['avg'] - res_hub['avg'])
        jit_diff = max(0.1, abs(res_dst['jitter'] - res_hub['jitter']))
        
        hub_info = get_node_by_ip(hub_ip)
        dst_info = get_node_by_ip(dst_ip)

        return {
            "measurement": "exec_twamp",
            # --- TAGS FUNDAMENTALES ---
            "cliente": dst_info["group"],   # Este es el tag para el tagpass de Telegraf
            "hub_origin": hub_info["name"],
            "target_node": dst_info["name"],
            "path": f"{hub_info['name']}->{dst_info['name']}",
            # --- FIELDS ---
            "roundTripTimeAverage": rtt_diff,
            "twoWayJitter": jit_diff,
            "rtt_total_server": res_dst['avg'],
            "sample_is_valid": 1.0,
            # --- GEODATA ---
            "src_latitude": hub_info["lat"],
            "src_longitude": hub_info["lon"],
            "dst_latitude": dst_info["lat"],
            "dst_longitude": dst_info["lon"]
        }
    else:
        return {"measurement": "exec_twamp", "sample_is_valid": 0.0, "cliente": "error"}

if __name__ == "__main__":
    print(json.dumps(main()))

