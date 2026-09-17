INSERT INTO `game_config`
    (`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'Game Mechanics', 'java.lang.Integer', 'monster_vac_duration_minutes', '10',
       '怪物吸星大法持续时间（分钟）', CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'monster_vac_duration_minutes'
);

INSERT INTO `lang_resources` (`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'zh-CN', 'game_config', 'monster_vac_duration_minutes', '怪物吸星大法持续时间（分钟）', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources`
    WHERE `lang_type` = 'zh-CN' AND `lang_base` = 'game_config'
      AND `lang_code` = 'monster_vac_duration_minutes'
);

INSERT INTO `lang_resources` (`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'en-US', 'game_config', 'monster_vac_duration_minutes', 'Monster vacuum duration in minutes', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources`
    WHERE `lang_type` = 'en-US' AND `lang_base` = 'game_config'
      AND `lang_code` = 'monster_vac_duration_minutes'
);
