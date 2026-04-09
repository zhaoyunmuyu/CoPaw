-- ============================================================
-- CoPaw 备份任务数据库表
-- 创建时间: 2026-04-09
-- 说明: 用于存储备份和恢复任务的持久化记录
-- ============================================================

-- 设置字符集
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------
-- 表: swe_backup_task
-- 说明: 备份任务记录表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `swe_backup_task` (
    `task_id` VARCHAR(64) NOT NULL COMMENT '任务ID',
    `task_type` ENUM('backup', 'restore') NOT NULL COMMENT '任务类型',
    `tenant_id` VARCHAR(64) DEFAULT NULL COMMENT '租户ID (可选)',
    `status` ENUM('pending', 'running', 'completed', 'failed', 'rolling_back', 'rolled_back') NOT NULL DEFAULT 'pending' COMMENT '任务状态',
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `started_at` TIMESTAMP NULL DEFAULT NULL COMMENT '开始时间',
    `completed_at` TIMESTAMP NULL DEFAULT NULL COMMENT '完成时间',

    -- 输入参数
    `target_tenant_ids` JSON DEFAULT NULL COMMENT '目标租户ID列表',
    `backup_date` VARCHAR(10) DEFAULT NULL COMMENT '备份日期 (YYYY-MM-DD)',
    `backup_hour` INT DEFAULT NULL COMMENT '备份小时 (0-23)',
    `instance_id` VARCHAR(64) DEFAULT NULL COMMENT '实例ID',

    -- 进度信息
    `current_step` VARCHAR(256) DEFAULT '' COMMENT '当前步骤描述',
    `progress_percent` INT NOT NULL DEFAULT 0 COMMENT '进度百分比 (0-100)',
    `processed_tenants` INT NOT NULL DEFAULT 0 COMMENT '已处理租户数',
    `total_tenants` INT NOT NULL DEFAULT 0 COMMENT '总租户数',

    -- 结果信息
    `s3_keys` JSON DEFAULT NULL COMMENT 'S3存储路径列表',
    `local_zip_paths` JSON DEFAULT NULL COMMENT '本地ZIP路径列表',
    `error_message` TEXT DEFAULT NULL COMMENT '错误信息',
    `rollback_data_paths` JSON DEFAULT NULL COMMENT '回滚数据路径列表',
    `restored_tenants` JSON DEFAULT NULL COMMENT '已恢复租户列表',

    PRIMARY KEY (`task_id`),
    INDEX `idx_task_type` (`task_type`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`),
    INDEX `idx_backup_date` (`backup_date`),
    INDEX `idx_instance_id` (`instance_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='备份任务记录表';

SET FOREIGN_KEY_CHECKS = 1;