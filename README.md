# TimeMap-CSUC: Automated Multi-Client Network Performance Monitoring

## Descripción
TimeMap es una solución avanzada de **"Latency & Jitter weathermap"** diseñada para transformar métricas complejas de telemetría de red en una visualización topológica dinámica e intuitiva. El sistema está optimizado para supervisar en tiempo real la salud de los enlaces de la **Anella Científica del CSUC**, midiendo parámetros críticos como el retardo y la variación del mismo mediante sondas activas y pasivas.

Este repositorio contiene los scripts de orquestación y los modelos de visualización descritos en el informe técnico del TFG.

## Arquitectura del Sistema
El núcleo tecnológico se basa en el **Stack TIG** (Telegraf, InfluxDB, Grafana) desplegado mediante contenedores **Docker**:

1.  **Telegraf:** Orquestador de recolección que ejecuta scripts personalizados.
2.  **InfluxDB 2.x:** "Data Lake" de series temporales con almacenamiento segmentado por clientes.
3.  **Grafana:** Capa de visualización que utiliza variables dinámicas para el aislamiento institucional (Multi-tenancy).

## Estructura del Repositorio
Para facilitar la navegación técnica, el código se organiza de la siguiente manera:

*   **/automation**: Scripts de Python para el aprovisionamiento masivo de clientes, creación de buckets, tokens de seguridad y organizaciones en Grafana a partir de fuentes Excel.
*   **/probes**: Sondas de medición basadas en **SNMP** (para routers Cisco/Juniper) y **TWAMP** (vía binario twping) para obtener métricas con precisión de microsegundos.
*   **/dashboards**: Modelos JSON maestros de Grafana, incluyendo el mapa topológico general y paneles detallados de latencia/jitter.
*   **/config**: Archivos base de configuración para el despliegue del stack, incluyendo `docker-compose.yml` y `telegraf.conf`.

## Características Principales
*   **Telemetría de Precisión:** Uso del estándar TWAMP (RFC 5357) para detectar asimetrías y micro-cortes.
*   **Aislamiento Total:** Implementación de *Scoped Tokens* y organizaciones estancas para garantizar la privacidad de datos entre instituciones.
*   **Sincronización Crítica:** Configuración jerárquica de tiempo mediante Chrony/NTP, esencial para mediciones unidireccionales (*One-way delay*).
*   **Escalabilidad:** Capacidad para gestionar más de 100 clientes de forma programática y sin errores manuales.

## Requisitos de Despliegue
*   **Hardware:** 4 vCPU, 8 GB RAM.
*   **Software:** Docker, Docker Compose y Python 3.x con librerías Pandas y InfluxDB-Client.

---
*Este proyecto forma parte de un Trabajo de Fin de Grado y ha sido validado en un entorno de laboratorio emulado con EVE-NG.*
