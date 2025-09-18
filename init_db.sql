DROP DATABASE IF EXISTS taskdb;
CREATE DATABASE taskdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE taskdb;

-- Tabla usuarios
CREATE TABLE user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user'
);

-- Tabla tareas con descripción
CREATE TABLE task (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT, -- 👈 agregado de nuevo
    status VARCHAR(20) DEFAULT 'Por hacer',
    user_id INT,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE SET NULL
);
-- Usuario admin inicial
INSERT INTO user (username, password, role) 
VALUES ('admin', 'admin', 'admin');

select * from user;
select * from task;

INSERT INTO task (title, description, status, user_id) 
VALUES ('Tarea de prueba', 'Probando dashboard', 'Por hacer', 1);