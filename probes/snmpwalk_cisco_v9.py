#! /usr/bin/env python3
import sys
import json
import argparse
import subprocess
from datetime import datetime

# --- 1. DICCIONARIO DE GEOLOCALIZACIÓN CSUC ---
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

# OIDs Oficiales Cisco RTTMON
SLA_TAG_OID = ".1.3.6.1.4.1.9.9.42.1.2.1.1.3"
SLA_SENSE_OID = ".1.3.6.1.4.1.9.9.42.1.2.10.1.2"
RTT_JITTER_BASE = ".1.3.6.1.4.1.9.9.42.1.5.2.1"

# Mapeo de métricas con Mayúsculas para InfluxDB/Grafana
# --- MAPEO FINAL VALIDADOS POR SNMPWALK (IOS 15.2) ---

METRICS_MAP = {
    "5":  "roundTripTimeAverage",
    "4":  "roundTripTimeMin",
    "2":  "roundTripTimeMax",
    "15": "roundTripTimeStdDev",
    "11": "posRttJitterAverage",
    "13": "posRttJitterMin",
    "12": "posRttJitterMax",
    "16": "posRttJitterStdDev",
    "19": "negRttJitterAverage",
    "18": "negRttJitterMin",
    "14": "negRttJitterMax",
    "20": "negRttJitterStdDev",
    "33": "ingressAverage", 
    "35": "ingressMin",
    "34": "ingressMax",
    "37": "egressAverage",
    "36": "egressMin",
    "38": "egressMax",
}

def run_snmp_walk(ip, community, oid):
    try:
        cmd = ["snmpwalk", "-v2c", "-c", community, "-On", ip, oid]
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8")
        return result.splitlines()
    except:
        return []

def fetch_data(ip, community):
    results = {}
    now = datetime.utcnow().isoformat()

    # 1. Identificar SLAs y Tags
    lines = run_snmp_walk(ip, community, SLA_TAG_OID)
    for line in lines:
        if "STRING:" in line:
            parts = line.split(" = STRING: ")
            sla_id = parts[0].split(".")[-1]
            tag_name = parts[1].strip(' "') # Limpia comillas y espacios

            if "--" in tag_name:
                tag_parts = tag_name.split("--")
                if len(tag_parts) == 3:
                    cliente = tag_parts[0].strip()
                    short_src = tag_parts[1].strip()
                    short_dst = tag_parts[2].strip()
                    
                    # Buscar coordenadas en el nuevo diccionario CSUC
                    src_geo = CSUC_LOCATIONS.get(short_src, {"latitude": 0.0, "longitude": 0.0})
                    dst_geo = CSUC_LOCATIONS.get(short_dst, {"latitude": 0.0, "longitude": 0.0})

                    results[sla_id] = {
                        "measurement": "exec_snmp",
                        "time": now,
                        "cliente": cliente,
                        "src_short": short_src,
                        "dst_short": short_dst,
                        "src_latitude": float(src_geo["latitude"]),
                        "src_longitude": float(src_geo["longitude"]),
                        "dst_latitude": float(dst_geo["latitude"]),
                        "dst_longitude": float(dst_geo["longitude"]),
                        "sample_is_valid": 0.0 
                    }

    # 2. Verificar validez (OperSense)
    sense_lines = run_snmp_walk(ip, community, SLA_SENSE_OID)
    for line in sense_lines:
        if "INTEGER:" in line:
            sla_id = line.split(" = ")[0].split(".")[-1]
            sense_val = line.split(": ")[1].strip()
            if sla_id in results:
                results[sla_id]["sample_is_valid"] = 1.0 if sense_val == "1" else 0.0

    # 3. Recoger métricas
    metric_lines = run_snmp_walk(ip, community, RTT_JITTER_BASE)
    for line in metric_lines:
        if " = " in line and ":" in line:
            try:
                oid_full, val_part = line.split(" = ")
                val = val_part.split(": ")[1].strip()
                oid_parts = oid_full.split(".")
                m_type = oid_parts[-2]
                sla_id = oid_parts[-1]
                
                if sla_id in results and m_type in METRICS_MAP:
                    results[sla_id][METRICS_MAP[m_type]] = float(val)
            except: continue

    # Rellenar con 0.0 los campos que falten para mantener consistencia en InfluxDB
    required_fields = list(METRICS_MAP.values())
    for sla in results.values():
        for field in required_fields:
            if field not in sla:
                sla[field] = 0.0

    return list(results.values())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("device_ip")
    parser.add_argument("snmp_community")
    args = parser.parse_args()

    data = fetch_data(args.device_ip, args.snmp_community)
    print(json.dumps(data))
