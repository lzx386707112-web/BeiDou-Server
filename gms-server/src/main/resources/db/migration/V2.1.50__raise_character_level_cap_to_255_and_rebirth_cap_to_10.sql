UPDATE `game_config`
SET `config_value` = '255'
WHERE `config_code` IN ('mxj_max_level', 'qst_max_level');

UPDATE `game_config`
SET `config_value` = '10'
WHERE `config_code` = 'max_reborn_count';
