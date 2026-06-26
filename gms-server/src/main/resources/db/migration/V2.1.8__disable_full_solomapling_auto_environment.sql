UPDATE `game_config`
SET `config_value` = 'false', `update_time` = NOW()
WHERE `config_code` = 'solo_mapling_auto_environment';
