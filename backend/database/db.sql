-- ============================================
-- DATABASE CREATION
-- ============================================
CREATE DATABASE IF NOT EXISTS cap2_csp_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cap2_csp_db;

-- ============================================
-- TABLES: ROLES & USERS (Giữ nguyên)
-- ============================================
CREATE TABLE `roles` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `role_name` VARCHAR(20) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `users` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `role_id` INT DEFAULT NULL,
  `username` VARCHAR(50) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `email` VARCHAR(100) NOT NULL UNIQUE,
  `full_name` VARCHAR(100) DEFAULT NULL,
  `telegram_chat_id` VARCHAR(50) DEFAULT NULL,
  `language` VARCHAR(5) DEFAULT 'vi',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_users_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLES: CAMERAS (Giữ nguyên)
-- ============================================
CREATE TABLE `cameras` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `camera_name` VARCHAR(100) NOT NULL,
  `rtsp_url` TEXT NOT NULL,
  `status` VARCHAR(20) DEFAULT 'offline',
  `is_active` BOOLEAN DEFAULT TRUE,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLES: ZONES (THAY ĐỔI QUAN TRỌNG)
-- ============================================
CREATE TABLE `zones` (
  `id` VARCHAR(50) NOT NULL, -- Đồng bộ với DPZ-01, DPZ-02 từ React
  `camera_id` INT NOT NULL,
  `zone_name` VARCHAR(100) DEFAULT NULL,
  `coordinates` JSON DEFAULT NULL, -- Lưu mảng [{x, y}, ...]
  `min_child_height` INT DEFAULT 50, -- Chuyển từ ai_settings sang để tùy biến từng vùng
  `sensitivity` FLOAT DEFAULT 0.5,    -- Chuyển từ ai_settings sang
  `is_active` BOOLEAN DEFAULT TRUE,
  PRIMARY KEY (`id`, `camera_id`), -- Khóa chính kết hợp để tránh trùng ID trên cùng 1 cam
  CONSTRAINT `fk_zones_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLES: AI SETTINGS (Chỉ giữ lại cài đặt chung cho Camera)
-- ============================================
CREATE TABLE `ai_settings` (
  `camera_id` INT NOT NULL,
  `enable_siren` BOOLEAN DEFAULT FALSE,
  `enable_telegram` BOOLEAN DEFAULT TRUE,
  `alert_cooldown` INT DEFAULT 30, -- Giây nghỉ giữa các lần báo động tránh spam
  PRIMARY KEY (`camera_id`),
  CONSTRAINT `fk_ai_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================
-- TABLES: ALERTS (Bổ sung để tracking vùng vi phạm)
-- ============================================
CREATE TABLE `alerts` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `camera_id` INT DEFAULT NULL,
  `zone_id` VARCHAR(50) DEFAULT NULL, -- Link tới vùng bị xâm nhập
  `object_type` ENUM('Child', 'Adult') DEFAULT 'Child',
  `confidence` FLOAT DEFAULT NULL,
  `image_path` VARCHAR(255) DEFAULT NULL,
  `video_path` VARCHAR(255) DEFAULT NULL,
  `is_resolved` BOOLEAN DEFAULT FALSE,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_alerts_camera` FOREIGN KEY (`camera_id`) REFERENCES `cameras` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_alerts_zone` FOREIGN KEY (`zone_id`) REFERENCES `zones` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Các bảng user_camera_access, notification_logs, system_health giữ nguyên như cũ...