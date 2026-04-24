-- ============================================================
-- 迁移脚本：修改 swe_tenant_init_source 表的唯一约束
-- 从 tenant_id 唯一改为 (tenant_id, source_id) 组合唯一
-- ============================================================

-- 1. 删除旧的唯一约束
ALTER TABLE swe_tenant_init_source DROP INDEX uk_tenant_id;

-- 2. 添加新的组合唯一约束
ALTER TABLE swe_tenant_init_source ADD UNIQUE KEY uk_tenant_source (tenant_id, source_id);
