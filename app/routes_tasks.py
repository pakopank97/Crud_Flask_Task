# app/routes_tasks.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .models import db, Task, User, VALID_STATUSES

import os
import requests
from requests.auth import HTTPBasicAuth

# -----------------------------
# Blueprint
# -----------------------------
tasks_bp = Blueprint("tasks", __name__)

# -----------------------------
# Estados permitidos por rol
# -----------------------------
ADMIN_ALLOWED_STATUSES = ["Por hacer", "Revisar", "Finalizar", "Liberada", "No completada"]
USER_ALLOWED_STATUSES = ["Por hacer", "Revisar", "Finalizar"]

def allowed_for_role(role: str):
    return ADMIN_ALLOWED_STATUSES if role == "admin" else USER_ALLOWED_STATUSES

# -----------------------------
# Configuración KIE Server / jBPM
# -----------------------------
KIE_SERVER_URL = os.getenv("KIE_SERVER_URL", "http://localhost:8080/kie-server/services/rest/server")
KIE_USER = os.getenv("KIE_USER", "wbadmin")
KIE_PASSWORD = os.getenv("KIE_PASSWORD", "wbadmin")

CONTAINER_ID = os.getenv("KIE_CONTAINER_ID", "tasks-kjar_1.0.0-SNAPSHOT")
PROCESS_ID = os.getenv("KIE_PROCESS_ID", "tasks-kjar.task-process")

# -----------------------------
# Funciones jBPM
# -----------------------------
def start_jbpm_process(task: Task):
    """Inicia proceso solo una vez por tarea."""
    url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/processes/{PROCESS_ID}/instances"
    payload = {
        "variables": {
            "taskId": {"value": task.id},
            "title": {"value": task.title},
            "description": {"value": task.description or ""},
            "status": {"value": task.status},
            "userId": {"value": task.user_id},
            "byUser": {"value": getattr(current_user, 'username', 'system')}
        }
    }
    try:
        r = requests.post(
            url,
            auth=HTTPBasicAuth(KIE_USER, KIE_PASSWORD),
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if r.status_code == 201:
            instance_id = int(r.text.strip())
            task.process_instance_id = instance_id
            db.session.commit()
            print(f"[jBPM] ✅ Proceso creado (ID={instance_id}) para tarea {task.id}")
        else:
            print(f"[jBPM] ❌ Error creando proceso ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"[jBPM] ❌ Error al conectar con jBPM: {e}")


def signal_jbpm_process(task: Task, signal_name="status_changed"):
    """Envía una señal JSON válida (evita error 415)."""
    if not task.process_instance_id:
        print(f"[jBPM] ⚠️ No hay process_instance_id en tarea {task.id}")
        return

    url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/processes/instances/{task.process_instance_id}/signal/{signal_name}"
    try:
        r = requests.post(
            url,
            auth=HTTPBasicAuth(KIE_USER, KIE_PASSWORD),
            json={},  # cuerpo JSON vacío
            headers={"Content-Type": "application/json"},
            timeout=6
        )
        if r.status_code in (200, 204):
            print(f"[jBPM] 🔁 Señal '{signal_name}' enviada a proceso {task.process_instance_id}")
        else:
            print(f"[jBPM] ⚠️ Error al enviar señal ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"[jBPM] ❌ Error conectando con jBPM: {e}")


def complete_jbpm_process(task: Task):
    """Finaliza proceso correctamente (no aborta)."""
    if not task.process_instance_id:
        print(f"[jBPM] ⚠️ No hay process_instance_id en tarea {task.id}")
        return

    url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/processes/instances/{task.process_instance_id}/signal/complete"
    try:
        r = requests.post(
            url,
            auth=HTTPBasicAuth(KIE_USER, KIE_PASSWORD),
            json={},  # cuerpo vacío válido
            headers={"Content-Type": "application/json"},
            timeout=6
        )
        if r.status_code in (200, 204):
            print(f"[jBPM] 🏁 Proceso {task.process_instance_id} finalizado correctamente.")
        else:
            print(f"[jBPM] ⚠️ Error al finalizar proceso ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"[jBPM] ❌ Error finalizando proceso: {e}")

# -----------------------------
# Dashboard y rutas
# -----------------------------
@tasks_bp.route("/")
@login_required
def dashboard():
    if current_user.role == "admin":
        tasks = Task.query.order_by(Task.id.desc()).all()
        users = User.query.order_by(User.username.asc()).all()
        can_create = True
        allowed_statuses = ADMIN_ALLOWED_STATUSES
    else:
        tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.id.desc()).all()
        users = []
        can_create = False
        allowed_statuses = USER_ALLOWED_STATUSES

    return render_template("dashboard.html", tasks=tasks, users=users, can_create=can_create, allowed_statuses=allowed_statuses)

# -----------------------------
# Crear tarea (solo admin)
# -----------------------------
@tasks_bp.route("/create", methods=["POST"])
@login_required
def create_task():
    if current_user.role != "admin":
        flash("Solo los administradores pueden crear tareas.", "danger")
        return redirect(url_for("tasks.dashboard"))

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    user_id = request.form.get("user_id")

    if not title or not user_id:
        flash("El título y el usuario asignado son obligatorios.", "danger")
        return redirect(url_for("tasks.dashboard"))

    task = Task(title=title, description=description, status="Por hacer", user_id=int(user_id))
    db.session.add(task)
    db.session.commit()

    start_jbpm_process(task)
    flash("Tarea creada correctamente.", "success")
    return redirect(url_for("tasks.dashboard"))

# -----------------------------
# Editar tarea (solo admin)
# -----------------------------
@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    """Permite al admin editar título, descripción o usuario asignado."""
    task = Task.query.get_or_404(task_id)

    if current_user.role != "admin":
        flash("Solo los administradores pueden editar tareas.", "danger")
        return redirect(url_for("tasks.dashboard"))

    if request.method == "POST":
        task.title = request.form.get("title", task.title)
        task.description = request.form.get("description", task.description)
        uid = request.form.get("user_id", task.user_id)
        try:
            task.user_id = int(uid)
        except Exception:
            pass

        db.session.commit()
        flash("Tarea actualizada correctamente.", "success")
        return redirect(url_for("tasks.dashboard"))

    users = User.query.order_by(User.username.asc()).all()
    return render_template("edit_task.html", task=task, users=users)

    # -----------------------------
# Eliminar tarea (solo admin)
# -----------------------------
@tasks_bp.route("/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    """Elimina una tarea (solo para administradores)."""
    task = Task.query.get_or_404(task_id)

    if current_user.role != "admin":
        flash("Solo los administradores pueden eliminar tareas.", "danger")
        return redirect(url_for("tasks.dashboard"))

    # Si tiene proceso jBPM asociado, lo abortamos limpiamente
    if getattr(task, "process_instance_id", None):
        try:
            url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/processes/instances/{task.process_instance_id}"
            r = requests.delete(url, auth=HTTPBasicAuth(KIE_USER, KIE_PASSWORD), timeout=6)
            if r.status_code in (200, 204):
                print(f"[jBPM] 🧹 Proceso {task.process_instance_id} abortado antes de eliminar tarea.")
            else:
                print(f"[jBPM] ⚠️ No se pudo abortar el proceso ({r.status_code}): {r.text}")
        except Exception as e:
            print(f"[jBPM] ❌ Error al abortar proceso: {e}")

    # Eliminar la tarea de la BD
    db.session.delete(task)
    db.session.commit()
    flash("Tarea eliminada correctamente.", "success")
    return redirect(url_for("tasks.dashboard"))


# -----------------------------
# Cambiar estado
# -----------------------------
@tasks_bp.route("/<int:task_id>/status", methods=["POST"])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    new_status = (request.form.get("status") or "").strip()

    allowed = allowed_for_role(current_user.role)
    if new_status not in allowed or new_status not in VALID_STATUSES:
        flash("Estado no permitido para tu rol.", "danger")
        return redirect(url_for("tasks.dashboard"))

    task.set_status(new_status)
    db.session.commit()

    # Envía señal al proceso si existe
    signal_jbpm_process(task, "status_changed")

    # Si está liberada → finaliza proceso
    if new_status == "Liberada":
        complete_jbpm_process(task)

    flash("Estado de tarea actualizado.", "success")
    return redirect(url_for("tasks.dashboard"))

# -----------------------------
# Página HTML “Ver todas”
# -----------------------------
@tasks_bp.route("/list", endpoint="all_tasks_page")
@login_required
def all_tasks_page():
    """Muestra todas las tareas (vista HTML)."""
    if current_user.role == "admin":
        tasks = Task.query.order_by(Task.id.desc()).all()
        allowed_statuses = ADMIN_ALLOWED_STATUSES
    else:
        tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.id.desc()).all()
        allowed_statuses = USER_ALLOWED_STATUSES

    return render_template("all_tasks.html", tasks=tasks, allowed_statuses=allowed_statuses)


# -----------------------------
# API JSON para dashboard
# -----------------------------
@tasks_bp.route("/all", methods=["GET"], endpoint="all_tasks_json")
@login_required
def all_tasks_json():
    """Devuelve todas las tareas en formato JSON (para frontend o API)."""
    if current_user.role == "admin":
        tasks = Task.query.order_by(Task.id.desc()).all()
    else:
        tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.id.desc()).all()

    data = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "user_id": t.user_id,
            "process_instance_id": getattr(t, "process_instance_id", None),
        }
        for t in tasks
    ]
    return jsonify(data)