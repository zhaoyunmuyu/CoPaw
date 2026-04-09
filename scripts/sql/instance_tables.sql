-- ============================================================
-- CoPaw 实例管理数据库表
-- 创建时间: 2026-04-08
-- 说明: 用于多实例管理和用户分配
-- ============================================================

-- 设置字符集
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------
-- 表: swe_instance_info
-- 说明: 实例信息表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `swe_instance_info` (
    `instance_id` VARCHAR(64) NOT NULL COMMENT '实例ID',
    `source_id` VARCHAR(64) NOT NULL COMMENT '来源ID',
    `bbk_id` VARCHAR(64) DEFAULT NULL COMMENT 'BBK ID (可选)',
    `instance_name` VARCHAR(128) NOT NULL COMMENT '实例名称',
    `instance_url` VARCHAR(512) NOT NULL COMMENT '实例访问URL',
    `max_users` INT NOT NULL DEFAULT 100 COMMENT '最大用户数',
    `status` ENUM('active', 'inactive') NOT NULL DEFAULT 'active' COMMENT '实例状态',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`instance_id`),
    INDEX `idx_source_id` (`source_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实例信息表';

-- -----------------------------------------------------------
-- 表: swe_instance_user
-- 说明: 用户分配表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `swe_instance_user` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '自增主键',
    `user_id` VARCHAR(128) NOT NULL COMMENT '用户ID',
    `source_id` VARCHAR(64) NOT NULL COMMENT '来源ID',
    `instance_id` VARCHAR(64) NOT NULL COMMENT '分配的实例ID',
    `allocated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '分配时间',
    `status` ENUM('active', 'migrated') NOT NULL DEFAULT 'active' COMMENT '分配状态',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_user_source` (`user_id`, `source_id`),
    INDEX `idx_instance_id` (`instance_id`),
    INDEX `idx_source_id` (`source_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_allocated_at` (`allocated_at`),
    CONSTRAINT `fk_instance_user_instance`
        FOREIGN KEY (`instance_id`)
        REFERENCES `swe_instance_info` (`instance_id`)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户分配表';

-- -----------------------------------------------------------
-- 表: swe_instance_log
-- 说明: 操作日志表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `swe_instance_log` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '自增主键',
    `action` VARCHAR(64) NOT NULL COMMENT '操作类型',
    `target_type` ENUM('source', 'instance', 'user') NOT NULL COMMENT '目标类型',
    `target_id` VARCHAR(128) NOT NULL COMMENT '目标ID',
    `old_value` JSON DEFAULT NULL COMMENT '旧值',
    `new_value` JSON DEFAULT NULL COMMENT '新值',
    `operator` VARCHAR(64) DEFAULT NULL COMMENT '操作者',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_action` (`action`),
    INDEX `idx_target` (`target_type`, `target_id`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_operator` (`operator`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志表';

-- -----------------------------------------------------------
-- 示例数据 (可选，用于测试)
-- -----------------------------------------------------------
-- INSERT INTO `swe_instance_info`
--     (`instance_id`, `source_id`, `instance_name`, `instance_url`, `max_users`)
-- VALUES
--     ('inst-default', 'default', '默认实例', 'http://localhost:8000', 100);

SET FOREIGN_KEY_CHECKS = 1;
