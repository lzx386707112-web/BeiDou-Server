INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT cfg.config_type, cfg.config_sub_type, cfg.config_clazz, cfg.config_code, cfg.config_value, cfg.config_desc, NOW()
FROM (
    SELECT 'server' config_type, 'SoloMapling' config_sub_type, 'java.lang.Boolean' config_clazz,
           'solo_mapling_bot_random_skill_enabled' config_code, 'true' config_value, 'solo_mapling_bot_random_skill_enabled' config_desc
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean',
           'solo_mapling_bot_random_chair_enabled', 'true', 'solo_mapling_bot_random_chair_enabled'
) cfg
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` g WHERE g.`config_code` = cfg.config_code
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT lang.lang_type, 'game_config', lang.lang_code, lang.lang_value, NULL
FROM (
    SELECT 'zh-CN' lang_type, 'solo_mapling_bot_random_skill_enabled' lang_code, '假人是否随机播放技能视觉效果' lang_value
    UNION ALL SELECT 'zh-CN', 'solo_mapling_bot_random_chair_enabled', '假人是否随机坐下或起身'
    UNION ALL SELECT 'en-US', 'solo_mapling_bot_random_skill_enabled', 'Allow bots to randomly play skill visual effects.'
    UNION ALL SELECT 'en-US', 'solo_mapling_bot_random_chair_enabled', 'Allow bots to randomly sit on or leave chairs.'
) lang
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` lr
    WHERE lr.`lang_type` = lang.lang_type
      AND lr.`lang_base` = 'game_config'
      AND lr.`lang_code` = lang.lang_code
);
