-- ============================================================
-- 租户初始化来源映射表
-- 记录每个租户(用户)的 source 和实际使用的初始化模板目录
-- ============================================================

CREATE TABLE IF NOT EXISTS swe_tenant_init_source (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tenant_id VARCHAR(128) NOT NULL COMMENT '租户ID（即用户ID）',
    source_id VARCHAR(64) NOT NULL COMMENT '用户访问来源（X-Source-Id）',
    init_source VARCHAR(64) NOT NULL COMMENT '实际使用的模板目录名（如 default_ruice）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uk_tenant_id (tenant_id),
    INDEX idx_source_id (source_id),
    INDEX idx_init_source (init_source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='租户初始化来源映射表';
