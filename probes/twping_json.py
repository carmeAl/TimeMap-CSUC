#! /usr/bin/python3

import os, sys, re, subprocess, json

# --- TABLA DE UBICACIONES Y CLIENTES CSUC ---
CSUC_LOCATIONS = {
    "servertimemap2": {"lat": 41.387713, "lon":2.111731 , "ip": "10.0.0.13", "group": "csuc"},
    "lapica": {"lat": 41.351687, "lon": 2.137114, "ip": "10.0.0.10", "port": 9000, "group": "csuc"},
    "pedraforca": {"lat": 41.387713, "lon": 2.111731, "ip": "10.0.0.2", "group": "csuc"},
    "uab": {"lat": 41.503718, "lon": 2.086401, "ip": "10.0.0.19", "group": "uab"},
    "uab-cs": {"lat": 41.54693, "lon": 2.11933, "ip": "10.0.0.23", "group": "uab"},
    "uab-r": {"lat": 41.54693, "lon": 2.11933, "ip": "10.0.0.24", "group": "uab"},
    "uao": {"lat": 41.409925, "lon": 2.12619, "ip": "10.0.0.25", "group": "uao"},
    "ub": {"lat": 41.38698, "lon": 2.16364, "ip": "10.0.0.26", "group": "ub"},
    "ub-ff": {"lat": 41.38698, "lon": 2.16364, "ip": "10.0.0.20", "group": "ub"},
    "udg": {"lat": 41.986008, "lon": 2.827307, "ip": "10.0.0.21", "group": "udg"},
    "udg-parcudg": {"lat": 41.96692, "lon": 2.83701, "ip": "10.0.0.22", "group": "udg"},
}

SERVER_IP = "10.0.0.13"

def get_node_by_ip(ip):
    for name, info in CSUC_LOCATIONS.items():
        if info["ip"] == ip:
            return {"name": name, **info}
    return {"name": ip, "lat": 0.0, "lon": 0.0, "group": "unknown"}

def parse_twping(raw_output):
    data = {}
    
    # 1. Paquetes enviados, perdidos y porcentaje
    loss_match = re.search(r'(\d+)\s+sent,\s+(\d+)\s+lost\s+\(([\d\.]+)%\)', raw_output)
    if loss_match:
        data['packets_sent'] = int(loss_match.group(1))
        data['packets_lost'] = int(loss_match.group(2))
        data['loss_percent'] = float(loss_match.group(3))

    # 2. RTT (Round-Trip Time) min/median/max
    rtt_match = re.search(r'round-trip time min/median/max\s+=\s+(-?[\d\.]+)/(-?[\d\.]+)/(-?[\d\.]+)', raw_output)
    if rtt_match:
        data['rtt_min'] = float(rtt_match.group(1))
        data['rtt_median'] = float(rtt_match.group(2))
        data['rtt_max'] = float(rtt_match.group(3))
        data['avg'] = data['rtt_median'] # Compatibilidad con lógica del hub

    # 3. Send time (Ida / Forward delay) min/median/max
    send_match = re.search(r'send time min/median/max\s+=\s+(-?[\d\.]+)/(-?[\d\.]+)/(-?[\d\.]+)', raw_output)
    if send_match:
        data['send_time_min'] = float(send_match.group(1))
        data['send_time_median'] = float(send_match.group(2))
        data['send_time_max'] = float(send_match.group(3))

    # 4. Reflect time (Vuelta / Backward delay) min/median/max
    reflect_match = re.search(r'reflect time min/median/max\s+=\s+(-?[\d\.]+)/(-?[\d\.]+)/(-?[\d\.]+)', raw_output)
    if reflect_match:
        data['reflect_time_min'] = float(reflect_match.group(1))
        data['reflect_time_median'] = float(reflect_match.group(2))
        data['reflect_time_max'] = float(reflect_match.group(3))

    # 5. Tiempo de procesado del Reflector min/max
    proc_match = re.search(r'reflector processing time min/max\s+=\s+(-?[\d\.]+)/(-?[\d\.]+)', raw_output)
    if proc_match:
        data['reflector_processing_min'] = float(proc_match.group(1))
        data['reflector_processing_max'] = float(proc_match.group(2))

    # 6. Jitters (Bidireccional, Ida y Vuelta)
    tw_jit = re.search(r'two-way jitter\s+=\s+(-?[\d\.]+)', raw_output)
    if tw_jit:
        data['jitter'] = float(tw_jit.group(1)) # Compatibilidad
        data['two_way_jitter_raw'] = data['jitter']

    s_jit = re.search(r'send jitter\s+=\s+(-?[\d\.]+)', raw_output)
    if s_jit: data['send_jitter'] = float(s_jit.group(1))

    r_jit = re.search(r'reflect jitter\s+=\s+(-?[\d\.]+)', raw_output)
    if r_jit: data['reflect_jitter'] = float(r_jit.group(1))

    return data

def run_twping(dip):
    node_info = get_node_by_ip(dip)
    port = node_info.get("port")
    twping_target = f"{dip}:{port}" if port else dip

    # Lanzamos 10 paquetes para tener buen muestreo de jitter sin colgar el timeout de Telegraf
    cmd = [
        "twping", 
        "-c", "10", 
        "-i", "0.1", 
        "-A", "O", 
        "-P", "10001-10010", 
        twping_target
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return parse_twping(result.stdout)
    except:
        return {}

def main():
    if len(sys.argv) < 3:
        return {"error": "Faltan argumentos"}
    
    hub_ip = sys.argv[1]
    dst_ip = sys.argv[2]

    # Inicialización por defecto si mide contra sí mismo
    if hub_ip == SERVER_IP or hub_ip == "127.0.0.1":
        res_hub = {
            'avg': 0.0, 'jitter': 0.0, 'rtt_min': 0.0, 'rtt_median': 0.0, 'rtt_max': 0.0,
            'send_time_min': 0.0, 'send_time_median': 0.0, 'send_time_max': 0.0,
            'reflect_time_min': 0.0, 'reflect_time_median': 0.0, 'reflect_time_max': 0.0,
            'reflector_processing_min': 0.0, 'reflector_processing_max': 0.0,
            'two_way_jitter_raw': 0.0, 'send_jitter': 0.0, 'reflect_jitter': 0.0,
            'packets_sent': 0, 'packets_lost': 0, 'loss_percent': 0.0
        }
    else:
        res_hub = run_twping(hub_ip)

    res_dst = run_twping(dst_ip)

    if 'avg' in res_hub and 'avg' in res_dst:
        # Cálculos diferenciales heredados
        rtt_diff = max(0.1, res_dst['avg'] - res_hub['avg'])
        jit_diff = max(0.1, abs(res_dst['jitter'] - res_hub['jitter']))
        
        hub_info = get_node_by_ip(hub_ip)
        dst_info = get_node_by_ip(dst_ip)

        return {
            "measurement": "exec_twamp",
            "cliente": dst_info["group"],   
            "src_ip": hub_ip,
            "dst_ip": dst_ip,
            "src_short": hub_info["name"],
            "dst_short": dst_info["name"],
            "sample_is_valid": 1.0,
            
            # Ubicaciones geométricas
            "src_latitude": hub_info["lat"],
            "src_longitude": hub_info["lon"],
            "dst_latitude": dst_info["lat"],
            "dst_longitude": dst_info["lon"],

            # Métricas calculadas / heredadas
            "roundTripTimeAverage": rtt_diff,
            "twoWayJitter": jit_diff,
            "rtt_total_server": res_dst['avg'],
            
            # --- NUEVAS MÉTRICAS DETALLADAS ---
            "packets_sent": res_dst.get("packets_sent", 0),
            "packets_lost": res_dst.get("packets_lost", 0),
            "loss_percent": res_dst.get("loss_percent", 0.0),
            
            "rtt_min": res_dst.get("rtt_min", 0.0),
            "rtt_median": res_dst.get("rtt_median", 0.0),
            "rtt_max": res_dst.get("rtt_max", 0.0),
            
            "send_time_min": res_dst.get("send_time_min", 0.0),
            "send_time_median": res_dst.get("send_time_median", 0.0),
            "send_time_max": res_dst.get("send_time_max", 0.0),
            
            "reflect_time_min": res_dst.get("reflect_time_min", 0.0),
            "reflect_time_median": res_dst.get("reflect_time_median", 0.0),
            "reflect_time_max": res_dst.get("reflect_time_max", 0.0),
            
            "reflector_processing_min": res_dst.get("reflector_processing_min", 0.0),
            "reflector_processing_max": res_dst.get("reflector_processing_max", 0.0),
            
            "two_way_jitter_raw": res_dst.get("two_way_jitter_raw", 0.0),
            "send_jitter": res_dst.get("send_jitter", 0.0),
            "reflect_jitter": res_dst.get("reflect_jitter", 0.0)
        }
    else:
        return {"measurement": "exec_twamp", "sample_is_valid": 0.0, "cliente": "error"}

if __name__ == "__main__":
    print(json.dumps(main()))
