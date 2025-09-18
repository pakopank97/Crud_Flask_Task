CREATE DATABASE IF NOT EXISTS taskdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'appuser'@'localhost' IDENTIFIED BY 'app_password';
GRANT ALL PRIVILEGES ON taskdb.* TO 'appuser'@'localhost';
FLUSH PRIVILEGES;

USE taskdb;
INSERT INTO user (username, password, role) VALUES ('admin', 'admin123', 'admin');
