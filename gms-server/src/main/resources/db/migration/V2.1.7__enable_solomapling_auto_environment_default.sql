UPDATE `game_config`
SET `config_value` = 'true', `update_time` = NOW()
WHERE `config_code` = 'solo_mapling_auto_environment';
