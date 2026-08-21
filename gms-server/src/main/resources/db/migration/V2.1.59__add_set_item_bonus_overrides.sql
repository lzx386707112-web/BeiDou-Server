INSERT INTO `game_config`
    (`config_type`, `config_sub_type`, `config_clazz`, `config_code`, `config_value`, `config_desc`, `update_time`)
SELECT 'server', 'Set Items', 'java.lang.String', 'set_item_bonus_overrides', '{}',
       'set_item_bonus_overrides', CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1 FROM `game_config` WHERE `config_code` = 'set_item_bonus_overrides'
);

INSERT INTO `lang_resources` (`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'zh-CN', 'game_config', 'set_item_bonus_overrides', '管理后台套装属性差异覆盖', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources`
    WHERE `lang_type` = 'zh-CN' AND `lang_base` = 'game_config'
      AND `lang_code` = 'set_item_bonus_overrides'
);

INSERT INTO `lang_resources` (`lang_type`, `lang_base`, `lang_code`, `lang_value`, `lang_extend`)
SELECT 'en-US', 'game_config', 'set_item_bonus_overrides', 'Admin set bonus overrides', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM `lang_resources`
    WHERE `lang_type` = 'en-US' AND `lang_base` = 'game_config'
      AND `lang_code` = 'set_item_bonus_overrides'
);
