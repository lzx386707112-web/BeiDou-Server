INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT cfg.config_type, cfg.config_sub_type, cfg.config_clazz, cfg.config_code, cfg.config_value, cfg.config_desc, NOW()
FROM (
    SELECT 'server' config_type, 'SoloMaplingMarket' config_sub_type, 'java.lang.Boolean' config_clazz,
           'solo_mapling_market_wander_enabled' config_code, 'true' config_value, 'solo_mapling_market_wander_enabled' config_desc
    UNION ALL SELECT 'server', 'SoloMaplingMarket', 'java.lang.Boolean', 'solo_mapling_market_hawk_enabled', 'true', 'solo_mapling_market_hawk_enabled'
    UNION ALL SELECT 'server', 'SoloMaplingMarket', 'java.lang.Boolean', 'solo_mapling_market_browse_shops_enabled', 'true', 'solo_mapling_market_browse_shops_enabled'
    UNION ALL SELECT 'server', 'SoloMaplingMarket', 'java.lang.Boolean', 'solo_mapling_market_idle_when_empty', 'true', 'solo_mapling_market_idle_when_empty'
    UNION ALL SELECT 'server', 'SoloMaplingMarket', 'java.lang.Integer', 'solo_mapling_market_tick_ms', '250', 'solo_mapling_market_tick_ms'
    UNION ALL SELECT 'server', 'SoloMaplingMarket', 'java.lang.Integer', 'solo_mapling_market_speech_gap_ms', '1200', 'solo_mapling_market_speech_gap_ms'
    UNION ALL SELECT 'server', 'SoloMaplingMarket', 'java.lang.Integer', 'solo_mapling_market_pathfind_per_tick', '3', 'solo_mapling_market_pathfind_per_tick'
) cfg
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` g WHERE g.`config_code` = cfg.config_code
);

UPDATE `game_config`
SET `config_sub_type` = 'SoloMaplingMarket', `update_time` = NOW()
WHERE `config_code` IN (
    'solo_mapling_feature_fm_bots_enabled',
    'solo_mapling_feature_fm_merchants_enabled',
    'solo_mapling_feature_fm_region_fill_enabled',
    'solo_mapling_market_bot_max',
    'solo_mapling_market_shop_max'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT lang.lang_type, 'game_config', lang.lang_code, lang.lang_value, NULL
FROM (
    SELECT 'zh-CN' lang_type, 'solo_mapling_market_wander_enabled' lang_code, '市场机器人是否闲逛走动' lang_value
    UNION ALL SELECT 'zh-CN', 'solo_mapling_market_hawk_enabled', '市场机器人是否叫卖喊话'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_market_browse_shops_enabled', '逛街机器人是否进店看货'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_market_idle_when_empty', '地图没有真实玩家时降低市场机器人频率'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_market_tick_ms', '市场机器人共享调度间隔毫秒'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_market_speech_gap_ms', '同一地图两次叫卖的最小间隔毫秒'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_market_pathfind_per_tick', '每个调度周期最多允许几只机器人寻路'
    UNION ALL SELECT 'en-US', 'solo_mapling_market_wander_enabled', 'Allow market bots to wander.'
    UNION ALL SELECT 'en-US', 'solo_mapling_market_hawk_enabled', 'Allow market bots to hawk items in chat.'
    UNION ALL SELECT 'en-US', 'solo_mapling_market_browse_shops_enabled', 'Allow browsing bots to enter shops.'
    UNION ALL SELECT 'en-US', 'solo_mapling_market_idle_when_empty', 'Slow market bots when no real players are on the map.'
    UNION ALL SELECT 'en-US', 'solo_mapling_market_tick_ms', 'Shared market bot scheduler interval in milliseconds.'
    UNION ALL SELECT 'en-US', 'solo_mapling_market_speech_gap_ms', 'Minimum milliseconds between hawking lines on the same map.'
    UNION ALL SELECT 'en-US', 'solo_mapling_market_pathfind_per_tick', 'Maximum pathfinds allowed per shared tick.'
) lang
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` lr
    WHERE lr.`lang_type` = lang.lang_type
      AND lr.`lang_base` = 'game_config'
      AND lr.`lang_code` = lang.lang_code
);
