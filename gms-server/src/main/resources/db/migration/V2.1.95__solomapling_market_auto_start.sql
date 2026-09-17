INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'SoloMaplingMarket', 'java.lang.Boolean', 'solo_mapling_market_auto_start', 'true', 'solo_mapling_market_auto_start', NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'solo_mapling_market_auto_start'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT lang.lang_type, 'game_config', lang.lang_code, lang.lang_value, NULL
FROM (
    SELECT 'zh-CN' lang_type, 'solo_mapling_market_auto_start' lang_code, '玩家进入自由市场时自动生成机器人和店铺' lang_value
    UNION ALL SELECT 'en-US', 'solo_mapling_market_auto_start', 'Automatically spawn market bots and shops when a player enters Free Market.'
) lang
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` lr
    WHERE lr.`lang_type` = lang.lang_type
      AND lr.`lang_base` = 'game_config'
      AND lr.`lang_code` = lang.lang_code
);
