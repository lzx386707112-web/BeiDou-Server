INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT lang.lang_type, 'game_config', lang.lang_code, lang.lang_value, NULL
FROM (
    SELECT 'zh-CN' lang_type, 'solo_mapling_market_auto_start' lang_code, '服务端启动后自动生成市场机器人和店铺，不依赖玩家进图' lang_value
    UNION ALL SELECT 'en-US', 'solo_mapling_market_auto_start', 'Spawn market bots and shops at server start, independent of players entering Free Market.'
) lang
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` lr
    WHERE lr.`lang_type` = lang.lang_type
      AND lr.`lang_base` = 'game_config'
      AND lr.`lang_code` = lang.lang_code
);

UPDATE `lang_resources`
SET `lang_value` = '服务端启动后自动生成市场机器人和店铺，不依赖玩家进图'
WHERE `lang_type` = 'zh-CN' AND `lang_base` = 'game_config' AND `lang_code` = 'solo_mapling_market_auto_start';

UPDATE `lang_resources`
SET `lang_value` = 'Spawn market bots and shops at server start, independent of players entering Free Market.'
WHERE `lang_type` = 'en-US' AND `lang_base` = 'game_config' AND `lang_code` = 'solo_mapling_market_auto_start';
