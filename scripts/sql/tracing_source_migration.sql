-- ============================================================
-- Tracing Source Isolation Migration
-- Date: 2026-04-17
-- Description: Add source_id field to Trace and Span tables for data isolation
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------
-- Migration 1: Add source_id to swe_tracing_traces table
-- -----------------------------------------------------------
-- Add source_id column (if not exists)
ALTER TABLE `swe_tracing_traces`
ADD COLUMN IF NOT EXISTS `source_id` VARCHAR(64) NOT NULL
COMMENT 'Source identifier for data isolation'
AFTER `trace_id`;

-- Add index on source_id for query performance
ALTER TABLE `swe_tracing_traces`
ADD INDEX IF NOT EXISTS `idx_source_id` (`source_id`);

-- Composite index for common queries (source_id + start_time)
ALTER TABLE `swe_tracing_traces`
ADD INDEX IF NOT EXISTS `idx_source_start_time` (`source_id`, `start_time`);

-- Composite index for source_id + user_id queries
ALTER TABLE `swe_tracing_traces`
ADD INDEX IF NOT EXISTS `idx_source_user` (`source_id`, `user_id`);

-- Composite index for source_id + session_id queries
ALTER TABLE `swe_tracing_traces`
ADD INDEX IF NOT EXISTS `idx_source_session` (`source_id`, `session_id`);

-- -----------------------------------------------------------
-- Migration 2: Add source_id to swe_tracing_spans table
-- -----------------------------------------------------------
-- Add source_id column (if not exists)
ALTER TABLE `swe_tracing_spans`
ADD COLUMN IF NOT EXISTS `source_id` VARCHAR(64) NOT NULL
COMMENT 'Source identifier for data isolation'
AFTER `span_id`;

-- Add index on source_id for query performance
ALTER TABLE `swe_tracing_spans`
ADD INDEX IF NOT EXISTS `idx_source_id` (`source_id`);

-- Composite index for common queries (source_id + start_time)
ALTER TABLE `swe_tracing_spans`
ADD INDEX IF NOT EXISTS `idx_source_start_time` (`source_id`, `start_time`);

-- Composite index for source_id + trace_id queries
ALTER TABLE `swe_tracing_spans`
ADD INDEX IF NOT EXISTS `idx_source_trace` (`source_id`, `trace_id`);

-- Composite index for source_id + user_id queries
ALTER TABLE `swe_tracing_spans`
ADD INDEX IF NOT EXISTS `idx_source_user` (`source_id`, `user_id`);

-- Composite index for source_id + session_id queries
ALTER TABLE `swe_tracing_spans`
ADD INDEX IF NOT EXISTS `idx_source_session` (`source_id`, `session_id`);

-- Composite index for skill detection (source_id + event_type + skill_name)
ALTER TABLE `swe_tracing_spans`
ADD INDEX IF NOT EXISTS `idx_source_skill` (`source_id`, `event_type`, `skill_name`);

-- Composite index for tool detection (source_id + event_type + tool_name)
ALTER TABLE `swe_tracing_spans`
ADD INDEX IF NOT EXISTS `idx_source_tool` (`source_id`, `event_type`, `tool_name`);

-- -----------------------------------------------------------
-- Important Notes:
-- 1. source_id is required (NOT NULL, no default value)
-- 2. Existing data needs to be updated with appropriate source_id before migration
-- 3. Example: UPDATE `swe_tracing_traces` SET `source_id` = 'portal' WHERE `source_id` = '';
-- -----------------------------------------------------------

SET FOREIGN_KEY_CHECKS = 1;