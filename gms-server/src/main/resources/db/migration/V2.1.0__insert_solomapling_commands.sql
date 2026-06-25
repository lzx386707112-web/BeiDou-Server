INSERT INTO command_info (syntax, level, enabled, clazz, default_level)
SELECT 'bot', 4, 1, 'ArtificialPlayerCommand', 4
WHERE NOT EXISTS (SELECT 1 FROM command_info WHERE syntax = 'bot');

INSERT INTO command_info (syntax, level, enabled, clazz, default_level)
SELECT 'move', 4, 1, 'BotMoveCommand', 4
WHERE NOT EXISTS (SELECT 1 FROM command_info WHERE syntax = 'move');

INSERT INTO command_info (syntax, level, enabled, clazz, default_level)
SELECT 'env', 4, 1, 'EnvironmentCommand', 4
WHERE NOT EXISTS (SELECT 1 FROM command_info WHERE syntax = 'env');

INSERT INTO command_info (syntax, level, enabled, clazz, default_level)
SELECT 'betafmshop', 4, 1, 'ArtificialFreeMarketCommand', 4
WHERE NOT EXISTS (SELECT 1 FROM command_info WHERE syntax = 'betafmshop');

INSERT INTO command_info (syntax, level, enabled, clazz, default_level)
SELECT 'fmbot', 4, 1, 'FMBotCommand', 4
WHERE NOT EXISTS (SELECT 1 FROM command_info WHERE syntax = 'fmbot');

INSERT INTO command_info (syntax, level, enabled, clazz, default_level)
SELECT 'tradebot', 4, 1, 'TradeBotTestCommand', 4
WHERE NOT EXISTS (SELECT 1 FROM command_info WHERE syntax = 'tradebot');

INSERT INTO command_info (syntax, level, enabled, clazz, default_level)
SELECT 'test', 4, 1, 'TestDevCommand', 4
WHERE NOT EXISTS (SELECT 1 FROM command_info WHERE syntax = 'test');

INSERT INTO command_info (syntax, level, enabled, clazz, default_level)
SELECT 'opq', 4, 1, 'OPQCommands', 4
WHERE NOT EXISTS (SELECT 1 FROM command_info WHERE syntax = 'opq');

INSERT INTO command_info (syntax, level, enabled, clazz, default_level)
SELECT 'reactor', 4, 1, 'ReactorCommands', 4
WHERE NOT EXISTS (SELECT 1 FROM command_info WHERE syntax = 'reactor');

INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'SoloMapling', 'java.lang.Boolean', 'solo_mapling_auto_environment', 'true', 'solo_mapling_auto_environment', NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'solo_mapling_auto_environment'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'zh-CN', 'game_config', 'solo_mapling_auto_environment', '是否在捕获 botClient 后自动加载 SoloMapling 环境', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` WHERE `lang_type` = 'zh-CN' AND `lang_code` = 'solo_mapling_auto_environment'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'en-US', 'game_config', 'solo_mapling_auto_environment', 'Automatically load the SoloMapling environment after botClient is captured.', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources` WHERE `lang_type` = 'en-US' AND `lang_code` = 'solo_mapling_auto_environment'
);
