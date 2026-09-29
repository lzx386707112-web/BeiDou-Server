-- 管理后台「套装属性」保存失败修复。
-- set_item_bonus_overrides / set_item_catalog_customizations 以 JSON 形式整条存放于
-- game_config.config_value，内容随「被改过的套装数 × 档位数 × 属性数」线性增长，
-- 原 varchar(256) 很快溢出，MySQL 严格模式直接报
--   Data truncation: Data too long for column 'config_value'
-- 进而让 SetItemController 的 PUT /setItem/latest/{definitionId} 返回 500。
-- 其它 JSON 型配置（如 job_buff_custom_time_list）同样会随时间增长，一并放宽。
ALTER TABLE `game_config`
    MODIFY COLUMN `config_value` MEDIUMTEXT NOT NULL COMMENT '参数值';
