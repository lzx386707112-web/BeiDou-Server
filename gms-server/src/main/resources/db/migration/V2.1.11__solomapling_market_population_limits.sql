INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT cfg.config_type, cfg.config_sub_type, cfg.config_clazz, cfg.config_code, cfg.config_value, cfg.config_desc, NOW()
FROM (
    SELECT 'server' config_type, 'SoloMapling' config_sub_type, 'java.lang.Integer' config_clazz,
           'solo_mapling_market_bot_max' config_code, '20' config_value, 'solo_mapling_market_bot_max' config_desc
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Integer',
           'solo_mapling_market_shop_max', '10', 'solo_mapling_market_shop_max'
) cfg
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` g WHERE g.`config_code` = cfg.config_code
);

UPDATE `game_config`
SET `config_value` = '30', `update_time` = NOW()
WHERE `config_code` = 'solo_mapling_environment_bot_max';

UPDATE `game_config`
SET `config_value` = '20', `update_time` = NOW()
WHERE `config_code` = 'solo_mapling_market_bot_max';

UPDATE `game_config`
SET `config_value` = '10', `update_time` = NOW()
WHERE `config_code` = 'solo_mapling_market_shop_max';

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT lang.lang_type, 'game_config', lang.lang_code, lang.lang_value, NULL
FROM (
    SELECT 'zh-CN' lang_type, 'solo_mapling_market_bot_max' lang_code, '自由市场入口最多生成多少个假人角色' lang_value
    UNION ALL SELECT 'zh-CN', 'solo_mapling_market_shop_max', '自由市场房间最多自动生成多少个开店摊位'
    UNION ALL SELECT 'en-US', 'solo_mapling_market_bot_max', 'Maximum bot characters spawned in the Free Market entrance.'
    UNION ALL SELECT 'en-US', 'solo_mapling_market_shop_max', 'Maximum auto-created shops in Free Market rooms.'
) lang
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` lr
    WHERE lr.`lang_type` = lang.lang_type
      AND lr.`lang_base` = 'game_config'
      AND lr.`lang_code` = lang.lang_code
);
