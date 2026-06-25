UPDATE `game_config`
SET `config_value` = 'true', `update_time` = NOW()
WHERE `config_code` IN (
    'solo_mapling_auto_environment',
    'solo_mapling_auto_map_bots_enabled'
);

UPDATE `command_info`
SET `enabled` = 1
WHERE `syntax` IN (
    'bot',
    'move',
    'env',
    'betafmshop',
    'fmbot',
    'tradebot',
    'test',
    'opq',
    'reactor'
);
