# -*- coding: utf-8 -*-
-- ============================================================
-- CoPaw 精选案例表合并迁移脚本
-- 执行时间: 需要在部署前手动执行
-- 说明: 将 swe_featured_case 和 swe_featured_case_config 合并为单表
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------
-- Step 1: 添加新字段到 swe_featured_case 表
-- -----------------------------------------------------------

-- 添加 source_id 字段（默认值为 'default'，后续可通过配置修改）
ALTER TABLE `swe_featured_case`
ADD COLUMN `source_id` VARCHAR(64) NOT NULL DEFAULT 'default' COMMENT '来源ID' AFTER `id`;

-- 添加 bbk_id 字段
ALTER TABLE `swe_featured_case`
ADD COLUMN `bbk_id` VARCHAR(64) DEFAULT NULL COMMENT 'BBK ID' AFTER `source_id`;

-- 添加 sort_order 字段
ALTER TABLE `swe_featured_case`
ADD COLUMN `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序序号' AFTER `steps`;

-- -----------------------------------------------------------
-- Step 2: 从 swe_featured_case_config 迁移数据（如果存在）
-- -----------------------------------------------------------

-- 将配置表中的维度信息更新到案例表
-- 注意：如果一个案例被多个维度配置引用，只会保留第一个配置的维度信息
UPDATE `swe_featured_case` c
JOIN `swe_featured_case_config` cc ON c.case_id = cc.case_id
SET c.source_id = cc.source_id,
    c.bbk_id = cc.bbk_id,
    c.sort_order = cc.sort_order
WHERE cc.is_active = 1;

-- -----------------------------------------------------------
-- Step 3: 删除旧的唯一键，创建新的唯一键
-- -----------------------------------------------------------

-- 删除旧的 case_id 唯一键
ALTER TABLE `swe_featured_case` DROP INDEX `uk_case_id`;

-- 创建新的组合唯一键
ALTER TABLE `swe_featured_case`
ADD UNIQUE KEY `uk_source_bbk_case` (`source_id`, `bbk_id`, `case_id`);

-- 添加索引
ALTER TABLE `swe_featured_case` ADD INDEX `idx_source_bbk` (`source_id`, `bbk_id`);

-- -----------------------------------------------------------
-- Step 4: 删除 swe_featured_case_config 表（可选，建议先保留观察）
-- -----------------------------------------------------------

-- 如果确认迁移成功，可以执行以下语句删除配置表
-- DROP TABLE IF EXISTS `swe_featured_case_config`;

-- 建议：先保留配置表，观察一段时间后再删除
-- 如果需要立即删除，取消注释上面的 DROP TABLE 语句

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 验证迁移结果
-- ============================================================

-- 查看迁移后的案例表结构
DESCRIBE `swe_featured_case`;

-- 查看迁移后的数据
SELECT source_id, bbk_id, case_id, label, sort_order FROM `swe_featured_case` LIMIT 10;