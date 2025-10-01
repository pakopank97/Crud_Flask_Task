import requests
from requests.auth import HTTPBasicAuth

KIE_SERVER_URL = "http://localhost:8080/kie-server/services/rest/server"
KIE_USER = "wbadmin"
KIE_PASSWORD = "wbadmin"
CONTAINER_ID = "tasks-kjar_1.0.0-SNAPSHOT"

def start_process(process_id, variables=None):
    url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/processes/{process_id}/instances"
    response = requests.post(url, auth=HTTPBasicAuth(KIE_USER, KIE_PASSWORD), json=variables or {})
    response.raise_for_status()
    return response.json()

def fire_rules(task_data):
    url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/ksession/rules"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, auth=HTTPBasicAuth(KIE_USER, KIE_PASSWORD), headers=headers, json={"objects": [task_data]})
    response.raise_for_status()
    return response.json()