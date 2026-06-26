INSERT INTO `game_config`(`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'SoloMapling', 'java.lang.Integer', 'solo_mapling_environment_bot_max', '80', 'solo_mapling_environment_bot_max', NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'solo_mapling_environment_bot_max'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'zh-CN', 'game_config', 'solo_mapling_environment_bot_max', '完整 SoloMapling 大环境最多生成多少个假人角色', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources`
    WHERE `lang_type` = 'zh-CN'
      AND `lang_base` = 'game_config'
      AND `lang_code` = 'solo_mapling_environment_bot_max'
);

INSERT INTO `lang_resources`(`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'en-US', 'game_config', 'solo_mapling_environment_bot_max', 'Maximum bot characters created by full SoloMapling environment startup.', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources`
    WHERE `lang_type` = 'en-US'
      AND `lang_base` = 'game_config'
      AND `lang_code` = 'solo_mapling_environment_bot_max'
);
