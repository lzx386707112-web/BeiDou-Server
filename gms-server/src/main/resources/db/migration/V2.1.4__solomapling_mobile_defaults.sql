UPDATE `game_config`
SET `config_value` = 'false', `update_time` = NOW()
WHERE `config_code` IN (
    'solo_mapling_auto_environment',
    'solo_mapling_henesys_bots_change_maps'
);

UPDATE `game_config`
SET `config_value` = 'true', `update_time` = NOW()
WHERE `config_code` = 'solo_mapling_auto_map_bots_enabled';
