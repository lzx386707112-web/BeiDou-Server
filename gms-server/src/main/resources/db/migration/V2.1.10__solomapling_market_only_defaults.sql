UPDATE `game_config`
SET `config_value` = 'true', `update_time` = NOW()
WHERE `config_code` IN (
    'solo_mapling_auto_map_bots_enabled',
    'solo_mapling_feature_fm_region_fill_enabled',
    'solo_mapling_feature_fm_bots_enabled',
    'solo_mapling_feature_fm_merchants_enabled',
    'solo_mapling_feature_gacha_bots_enabled',
    'solo_mapling_feature_opq_lobby_bots_enabled',
    'solo_mapling_feature_blackjack_tables_enabled',
    'solo_mapling_feature_casino_npc_enabled',
    'solo_mapling_feature_rps_npc_enabled',
    'solo_mapling_feature_conversation_enabled',
    'solo_mapling_feature_hot_potato_enabled'
);

UPDATE `game_config`
SET `config_value` = 'false', `update_time` = NOW()
WHERE `config_code` = 'solo_mapling_auto_environment';
