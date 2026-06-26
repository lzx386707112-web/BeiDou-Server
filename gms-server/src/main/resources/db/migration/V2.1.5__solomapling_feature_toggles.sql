INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT cfg.config_type, cfg.config_sub_type, cfg.config_clazz, cfg.config_code, cfg.config_value, cfg.config_desc, NOW()
FROM (
    SELECT 'server' config_type, 'SoloMapling' config_sub_type, 'java.lang.Boolean' config_clazz, 'solo_mapling_auto_map_bots_random_position' config_code, 'true' config_value, 'solo_mapling_auto_map_bots_random_position' config_desc
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_auto_map_bots_ambient_enabled', 'true', 'solo_mapling_auto_map_bots_ambient_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_auto_map_bots_move_enabled', 'true', 'solo_mapling_auto_map_bots_move_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_auto_map_bots_chat_enabled', 'true', 'solo_mapling_auto_map_bots_chat_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_auto_map_bots_emote_enabled', 'true', 'solo_mapling_auto_map_bots_emote_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_auto_map_bots_face_player_enabled', 'true', 'solo_mapling_auto_map_bots_face_player_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Integer', 'solo_mapling_auto_map_bots_action_min_ms', '2000', 'solo_mapling_auto_map_bots_action_min_ms'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Integer', 'solo_mapling_auto_map_bots_action_max_ms', '5000', 'solo_mapling_auto_map_bots_action_max_ms'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_bot_random_chinese_name', 'true', 'solo_mapling_bot_random_chinese_name'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_bot_random_body_enabled', 'true', 'solo_mapling_bot_random_body_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_bot_normal_equips_enabled', 'true', 'solo_mapling_bot_normal_equips_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_bot_full_equips_enabled', 'true', 'solo_mapling_bot_full_equips_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_bot_nx_equips_enabled', 'true', 'solo_mapling_bot_nx_equips_enabled'
    UNION ALL SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_bot_deferred_decoration_enabled', 'false', 'solo_mapling_bot_deferred_decoration_enabled'
) cfg
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` g WHERE g.`config_code` = cfg.config_code
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT lang.lang_type, 'game_config', lang.lang_code, lang.lang_value, NULL
FROM (
    SELECT 'zh-CN' lang_type, 'solo_mapling_auto_map_bots_random_position' lang_code, '自动假人是否在整张地图随机生成（关闭后按玩家附近半径生成）' lang_value
    UNION ALL SELECT 'zh-CN', 'solo_mapling_auto_map_bots_ambient_enabled', '自动假人是否启动站街行为定时器（关闭后只生成不行动，性能最低）'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_auto_map_bots_move_enabled', '自动假人是否随机走动'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_auto_map_bots_chat_enabled', '自动假人是否随机说话'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_auto_map_bots_emote_enabled', '自动假人是否随机表情'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_auto_map_bots_face_player_enabled', '自动假人是否转向附近玩家'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_auto_map_bots_action_min_ms', '自动假人两次行为之间的最小间隔毫秒'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_auto_map_bots_action_max_ms', '自动假人两次行为之间的最大间隔毫秒'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_bot_random_chinese_name', '假人是否使用随机中文名（关闭后使用原 SoloMapling 英文名池）'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_bot_random_body_enabled', '假人是否随机发型、脸型、肤色等身体外观'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_bot_normal_equips_enabled', '假人是否随机穿普通装备'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_bot_full_equips_enabled', '假人是否允许完整职业装备装扮（关闭后只用轻量快速装备）'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_bot_nx_equips_enabled', '假人是否随机穿 NX/点装外观'
    UNION ALL SELECT 'zh-CN', 'solo_mapling_bot_deferred_decoration_enabled', '是否启用延迟装扮队列（高数量假人时建议关闭）'
    UNION ALL SELECT 'en-US', 'solo_mapling_auto_map_bots_random_position', 'Spawn auto map bots at random positions across the map. Disabled uses nearby-player radius.'
    UNION ALL SELECT 'en-US', 'solo_mapling_auto_map_bots_ambient_enabled', 'Start the ambient behavior scheduler for auto map bots. Disable for lowest CPU use.'
    UNION ALL SELECT 'en-US', 'solo_mapling_auto_map_bots_move_enabled', 'Allow auto map bots to walk randomly.'
    UNION ALL SELECT 'en-US', 'solo_mapling_auto_map_bots_chat_enabled', 'Allow auto map bots to chat randomly.'
    UNION ALL SELECT 'en-US', 'solo_mapling_auto_map_bots_emote_enabled', 'Allow auto map bots to use random emotes.'
    UNION ALL SELECT 'en-US', 'solo_mapling_auto_map_bots_face_player_enabled', 'Allow auto map bots to face nearby players.'
    UNION ALL SELECT 'en-US', 'solo_mapling_auto_map_bots_action_min_ms', 'Minimum milliseconds between auto bot ambient actions.'
    UNION ALL SELECT 'en-US', 'solo_mapling_auto_map_bots_action_max_ms', 'Maximum milliseconds between auto bot ambient actions.'
    UNION ALL SELECT 'en-US', 'solo_mapling_bot_random_chinese_name', 'Use random Chinese bot names. Disabled uses the original SoloMapling English name pool.'
    UNION ALL SELECT 'en-US', 'solo_mapling_bot_random_body_enabled', 'Randomize bot hair, face, skin, and body appearance.'
    UNION ALL SELECT 'en-US', 'solo_mapling_bot_normal_equips_enabled', 'Randomize normal equipment for bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_bot_full_equips_enabled', 'Allow full class-aware equipment decoration. Disabled uses lightweight quick equip only.'
    UNION ALL SELECT 'en-US', 'solo_mapling_bot_nx_equips_enabled', 'Randomize NX/cash cosmetic equipment for bots.'
    UNION ALL SELECT 'en-US', 'solo_mapling_bot_deferred_decoration_enabled', 'Enable deferred decoration queue. Recommended off for large bot counts.'
) lang
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` lr
    WHERE lr.`lang_type` = lang.lang_type
      AND lr.`lang_base` = 'game_config'
      AND lr.`lang_code` = lang.lang_code
);
