from flask_login import UserMixin
from . import db

# Estados válidos del sistema (usados en backend, BPMN y vistas)
VALID_STATUSES = ("Por hacer", "Revisar", "Finalizar", "Liberada", "No completada")

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), default="user")

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Dejamos VARCHAR(20) pero validamos contra VALID_STATUSES en el backend
    status = db.Column(db.String(20), default="Por hacer", nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User", backref="tasks")

    def set_status(self, new_status):
        """Valida que el estado sea permitido antes de asignarlo"""
        if new_status not in VALID_STATUSES:
            raise ValueError(f"Estado '{new_status}' no es válido.")
        self.status = new_status