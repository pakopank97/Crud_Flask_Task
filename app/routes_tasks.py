# app/routes_tasks.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .models import db, Task, User, VALID_STATUSES

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
# Configuración fija del KIE Server / jBPM
# -----------------------------
KIE_SERVER_URL = "http://localhost:8080/kie-server/services/rest/server"
KIE_USER = "wbadmin"
KIE_PASSWORD = "wbadmin"

CONTAINER_ID = "tasks-kjar_1.0.0-SNAPSHOT"
PROCESS_ID = "tasks-kjar.task-process"

def notify_jbpm(event: str, task: Task):
    """Notifica al KIE Server pero no interrumpe el flujo en caso de error."""
    url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/processes/{PROCESS_ID}/instances"
    payload = {
        "event": event,
        "taskId": task.id,
        "title": task.title,
        "status": task.status,
        "userId": task.user_id,
        "byUser": getattr(current_user, "username", "system"),
    }
    try:
        r = requests.post(
            url,
            auth=HTTPBasicAuth(KIE_USER, KIE_PASSWORD),
            json=payload,
            timeout=6,
        )
        if r.status_code >= 400:
            print(f"[jBPM] {r.status_code} {r.text[:300]}")
        else:
            print(f"[jBPM] OK evento={event} tarea={task.id}")
    except Exception as e:
        print(f"[jBPM] Error notificando ({event}): {e}")

# -----------------------------
# Dashboard
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

    return render_template(
        "dashboard.html",
        tasks=tasks,
        users=users,
        can_create=can_create,
        allowed_statuses=allowed_statuses,
    )

# -----------------------------
# Página HTML “Ver todas”
# -----------------------------
@tasks_bp.route("/list", endpoint="all_tasks_page")
@login_required
def all_tasks_page():
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
        }
        for t in tasks
    ]
    return jsonify(data)

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

    notify_jbpm("created", task)

    flash("Tarea creada correctamente.", "success")
    return redirect(url_for("tasks.dashboard"))

# -----------------------------
# Editar tarea (solo admin)
# -----------------------------
@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
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

    task.status = new_status
    db.session.commit()

    notify_jbpm("status_changed", task)

    flash("Estado de tarea actualizado.", "success")
    return redirect(url_for("tasks.dashboard"))

# -----------------------------
# Eliminar tarea (solo admin)
# -----------------------------
@tasks_bp.route("/<int:task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)

    if current_user.role != "admin":
        flash("Solo los administradores pueden eliminar tareas.", "danger")
        return redirect(url_for("tasks.dashboard"))

    db.session.delete(task)
    db.session.commit()
    flash("Tarea eliminada correctamente.", "success")
    return redirect(url_for("tasks.dashboard"))
