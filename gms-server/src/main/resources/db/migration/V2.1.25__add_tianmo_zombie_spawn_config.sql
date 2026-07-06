INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT cfg.config_type, cfg.config_sub_type, cfg.config_clazz, cfg.config_code, cfg.config_value, cfg.config_desc, NOW()
FROM (
    SELECT 'server' config_type, 'Boss Events' config_sub_type, 'java.lang.Boolean' config_clazz,
           'tianmo_zombie_spawn_enabled' config_code, 'true' config_value, 'tianmo_zombie_spawn_enabled' config_desc
    UNION ALL
    SELECT 'server', 'Boss Events', 'java.lang.Integer',
           'tianmo_zombie_spawn_interval_minutes', '120', 'tianmo_zombie_spawn_interval_minutes'
) cfg
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` g WHERE g.`config_code` = cfg.config_code
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT lang.lang_type, 'game_config', lang.lang_code, lang.lang_value, NULL
FROM (
    SELECT 'zh-CN' lang_type, 'tianmo_zombie_spawn_enabled' lang_code, '是否启用天魔僵尸随机追杀事件' lang_value
    UNION ALL
    SELECT 'zh-CN', 'tianmo_zombie_spawn_interval_minutes', '天魔僵尸随机追杀事件触发间隔，单位分钟'
    UNION ALL
    SELECT 'en-US', 'tianmo_zombie_spawn_enabled', 'Enable the Tianmo Zombie random hunt event.'
    UNION ALL
    SELECT 'en-US', 'tianmo_zombie_spawn_interval_minutes', 'Trigger interval for the Tianmo Zombie random hunt event, in minutes.'
) lang
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` lr
    WHERE lr.`lang_type` = lang.lang_type
      AND lr.`lang_base` = 'game_config'
      AND lr.`lang_code` = lang.lang_code
);

-- Tianmo Zombie fixed rewards.
-- 4031866 is the existing 250 NX coupon; quantity 40 equals 10,000 NX on pickup.
INSERT INTO `drop_data` (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(9600318, 0, 10000000, 10000000, 0, 999999),
(9600318, 4031866, 40, 40, 0, 999999),
(9600318, 4021010, 30, 30, 0, 999999),
(9600318, 4310059, 30, 30, 0, 999999)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
