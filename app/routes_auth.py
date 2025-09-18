from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from .models import User
from . import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for("tasks.dashboard"))
        else:
            flash("Usuario o contraseña incorrectos")
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if current_user.role != "admin":
        flash("Solo el admin puede crear usuarios")
        return redirect(url_for("tasks.dashboard"))

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role", "user")
        if User.query.filter_by(username=username).first():
            flash("Ese usuario ya existe")
        else:
            new_user = User(username=username, password=password, role=role)
            db.session.add(new_user)
            db.session.commit()
            flash("Usuario creado con éxito")
            return redirect(url_for("tasks.dashboard"))

    return render_template("register.html")
