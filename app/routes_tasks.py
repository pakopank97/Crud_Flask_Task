from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .models import db, Task, User, VALID_STATUSES
import requests

tasks_bp = Blueprint("tasks", __name__)

# ================================
# Configuración del KIE Server (jBPM)
# ================================
KIE_SERVER_URL = "http://localhost:8080/kie-server/services/rest/server"
KIE_USER = "wbadmin"
KIE_PASSWORD = "wbadmin"

# Ajusta según tu contenedor/proceso en jBPM
CONTAINER_ID = "tasks-kjar_1.0.0-SNAPSHOT"
PROCESS_ID = "tasks-kjar.task-process"

def notify_jbpm(task_id, status):
    """
    Notifica a jBPM cuando una tarea se crea o cambia de estado.
    """
    url = f"{KIE_SERVER_URL}/containers/{CONTAINER_ID}/processes/{PROCESS_ID}/instances"
    payload = {"taskId": task_id, "status": status}
    try:
        response = requests.post(url, auth=(KIE_USER, KIE_PASSWORD), json=payload)
        response.raise_for_status()
        print(f"[jBPM] Proceso notificado para tarea {task_id} con estado '{status}'")
    except requests.exceptions.RequestException as e:
        print(f"[jBPM] Error notificando: {e}")

# ================================
# Definición de estados permitidos
# ================================
ADMIN_ALLOWED_STATUSES = ["Por hacer", "Revisar", "Finalizar", "Liberada", "No completada"]
USER_ALLOWED_STATUSES = ["Por hacer", "Revisar", "Finalizar"]

# ================================
# Rutas del CRUD de tareas
# ================================
@tasks_bp.route("/")
@login_required
def dashboard():
    # Si es admin, ve todas las tareas
    if current_user.role == "admin":
        tasks = Task.query.order_by(Task.id.desc()).all()
        users = User.query.order_by(User.username.asc()).all()
        can_create = True
        allowed_statuses = ADMIN_ALLOWED_STATUSES
    else:
        # Usuarios normales solo ven sus tareas
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

@tasks_bp.route("/create", methods=["POST"])
@login_required
def create_task():
    if current_user.role != "admin":
        flash("Solo los administradores pueden crear tareas.", "danger")
        return redirect(url_for("tasks.dashboard"))

    title = request.form.get("title")
    description = request.form.get("description")
    user_id = request.form.get("user_id")

    if not title or not user_id:
        flash("El título y el usuario asignado son obligatorios.", "danger")
        return redirect(url_for("tasks.dashboard"))

    task = Task(
        title=title,
        description=description,
        status="Por hacer",
        user_id=user_id,
    )
    db.session.add(task)
    db.session.commit()

    notify_jbpm(task.id, task.status)

    flash("Tarea creada correctamente.", "success")
    return redirect(url_for("tasks.dashboard"))

@tasks_bp.route("/<int:task_id>/status", methods=["POST"])
@login_required
def update_status(task_id):
    task = Task.query.get_or_404(task_id)
    new_status = request.form.get("status")

    allowed_statuses = ADMIN_ALLOWED_STATUSES if current_user.role == "admin" else USER_ALLOWED_STATUSES

    if new_status not in allowed_statuses or new_status not in VALID_STATUSES:
        flash("Estado no permitido.", "danger")
        return redirect(url_for("tasks.dashboard"))

    task.status = new_status
    db.session.commit()

    notify_jbpm(task.id, task.status)

    flash("Estado de tarea actualizado.", "success")
    return redirect(url_for("tasks.dashboard"))

@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if current_user.role != "admin":
        flash("Solo los administradores pueden editar tareas.", "danger")
        return redirect(url_for("tasks.dashboard"))

    if request.method == "POST":
        task.title = request.form.get("title")
        task.description = request.form.get("description")
        task.user_id = request.form.get("user_id")
        db.session.commit()
        flash("Tarea actualizada correctamente.", "success")
        return redirect(url_for("tasks.dashboard"))

    users = User.query.order_by(User.username.asc()).all()
    return render_template("edit_task.html", task=task, users=users)

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
