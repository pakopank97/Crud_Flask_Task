# app/jbpm_client.py
import os
import requests
from requests.auth import HTTPBasicAuth

# Configuración jBPM / KIE Server (puedes sobreescribir con variables de entorno)
KIE_SERVER_URL = os.getenv(
    "KIE_SERVER_URL",
    "http://localhost:8080/kie-server/services/rest/server"
)
KIE_USER = os.getenv("KIE_USER", "kie")
KIE_PASSWORD = os.getenv("KIE_PASSWORD", "kie123")

# IDs desplegados en Business Central
CONTAINER_ID = os.getenv("KIE_CONTAINER_ID", "tasks-kjar_1.0.0-SNAPSHOT")
PROCESS_ID = os.getenv("KIE_PROCESS_ID", "tasks-kjar.task-process")


def start_process(payload: dict):
    """
    Inicia un proceso en jBPM con un payload custom.
    """
    url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/processes/{PROCESS_ID}/instances"
    try:
        r = requests.post(url, auth=HTTPBasicAuth(KIE_USER, KIE_PASSWORD), json=payload, timeout=6)
        if r.status_code >= 400:
            print(f"[jBPM] Error {r.status_code}: {r.text[:300]}")
        else:
            print(f"[jBPM] Proceso iniciado OK → {r.text}")
    except Exception as e:
        print(f"[jBPM] Error al iniciar proceso: {e}")


def signal_event(instance_id: int, event_name: str, payload: dict):
    """
    Envía un evento a una instancia de proceso en jBPM.
    """
    url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/processes/instances/{instance_id}/signal/{event_name}"
    try:
        r = requests.post(url, auth=HTTPBasicAuth(KIE_USER, KIE_PASSWORD), json=payload, timeout=6)
        if r.status_code >= 400:
            print(f"[jBPM] Error evento {event_name}: {r.status_code} {r.text[:300]}")
        else:
            print(f"[jBPM] Evento '{event_name}' enviado a instancia {instance_id}")
    except Exception as e:
        print(f"[jBPM] Error enviando evento {event_name}: {e}")