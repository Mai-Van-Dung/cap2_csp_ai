-- ============================================
-- DATABASE CREATION
-- ============================================
CREATE DATABASE IF NOT EXISTS cap2_csp_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cap2_csp_db;

-- 1. Bảng vai trò
CREATE TABLE `roles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `role_name` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Bảng người dùng
CREATE TABLE `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `role_id` INT DEFAULT NULL,
  `username` VARCHAR(50) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `email` VARCHAR(100) NOT NULL,
  `full_name` VARCHAR(100) DEFAULT NULL,
  `telegram_chat_id` VARCHAR(50) DEFAULT NULL,
  `language` VARCHAR(5) DEFAULT 'vi',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`),
  CONSTRAINT `fk_users_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Bảng camera
CREATE TABLE `cameras` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `camera_name` VARCHAR(100) NOT NULL,
  `rtsp_url` TEXT NOT NULL,
  `status` VARCHAR(20) DEFAULT 'offline',
  `is_active` TINYINT(1) DEFAULT '1',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Bảng vùng giám sát
CREATE TABLE `zones` (
  `id` VARCHAR(50) NOT NULL,
  `camera_id` INT NOT NULL,
  `zone_name` VARCHAR(100) DEFAULT NULL,
  `coordinates` JSON DEFAULT NULL,
  `min_child_height` INT DEFAULT '50',
  `sensitivity` FLOAT DEFAULT '0.5',
  `is_active` TINYINT(1) DEFAULT '1',
  PRIMARY KEY (`id`, `camera_id`),
  CONSTRAINT `fk_zones_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Bảng cài đặt AI cho camera
CREATE TABLE `ai_settings` (
  `camera_id` INT NOT NULL,
  `enable_siren` TINYINT(1) DEFAULT '0',
  `enable_telegram` TINYINT(1) DEFAULT '1',
  `alert_cooldown` INT DEFAULT '30',
  PRIMARY KEY (`camera_id`),
  CONSTRAINT `fk_ai_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. Bảng quyền truy cập camera của người dùng
CREATE TABLE `user_camera_access` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `user_id` INT DEFAULT NULL,
  `camera_id` INT DEFAULT NULL,
  `access_level` ENUM('owner', 'viewer') DEFAULT 'viewer',
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_uca_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_uca_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. Bảng cảnh báo
CREATE TABLE `alerts` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `camera_id` INT DEFAULT NULL,
  `zone_id` VARCHAR(50) DEFAULT NULL,
  `object_type` ENUM('Child', 'Adult') DEFAULT 'Child',
  `confidence` FLOAT DEFAULT NULL,
  `image_path` VARCHAR(255) DEFAULT NULL,
  `video_path` VARCHAR(255) DEFAULT NULL,
  `is_resolved` TINYINT(1) DEFAULT '0',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),CONSTRAINT `fk_alerts_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_alerts_zone` FOREIGN KEY (`zone_id`) REFERENCES `zones` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. Bảng nhật ký thông báo
CREATE TABLE `notification_logs` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `alert_id` INT DEFAULT NULL,
  `user_id` INT DEFAULT NULL,
  `status` VARCHAR(20) DEFAULT NULL,
  `sent_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_notif_alert` FOREIGN KEY (`alert_id`) REFERENCES `alerts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_notif_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9. Bảng sức khỏe hệ thống
CREATE TABLE `system_health` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `camera_id` INT DEFAULT NULL,
  `event_type` VARCHAR(50) DEFAULT NULL,
  `message` TEXT,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_health_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4