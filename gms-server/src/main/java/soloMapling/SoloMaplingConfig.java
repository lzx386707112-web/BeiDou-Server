package soloMapling;

import org.gms.config.GameConfig;

public final class SoloMaplingConfig {
    private SoloMaplingConfig() {
    }

    public static final String AUTO_ENVIRONMENT = "solo_mapling_auto_environment";
    public static final String ENVIRONMENT_BOT_MAX = "solo_mapling_environment_bot_max";
    public static final String MARKET_BOT_MAX = "solo_mapling_market_bot_max";
    public static final String MARKET_SHOP_MAX = "solo_mapling_market_shop_max";
    public static final String AUTO_MAP_BOTS_ENABLED = "solo_mapling_auto_map_bots_enabled";
    public static final String AUTO_MAP_BOTS_MIN = "solo_mapling_auto_map_bots_min";
    public static final String AUTO_MAP_BOTS_MAX = "solo_mapling_auto_map_bots_max";
    public static final String AUTO_MAP_BOTS_RADIUS = "solo_mapling_auto_map_bots_radius";
    public static final String AUTO_MAP_BOTS_RANDOM_POSITION = "solo_mapling_auto_map_bots_random_position";
    public static final String AUTO_MAP_BOTS_AMBIENT_ENABLED = "solo_mapling_auto_map_bots_ambient_enabled";
    public static final String AUTO_MAP_BOTS_MOVE_ENABLED = "solo_mapling_auto_map_bots_move_enabled";
    public static final String AUTO_MAP_BOTS_CHAT_ENABLED = "solo_mapling_auto_map_bots_chat_enabled";
    public static final String AUTO_MAP_BOTS_EMOTE_ENABLED = "solo_mapling_auto_map_bots_emote_enabled";
    public static final String AUTO_MAP_BOTS_FACE_PLAYER_ENABLED = "solo_mapling_auto_map_bots_face_player_enabled";
    public static final String AUTO_MAP_BOTS_ACTION_MIN_MS = "solo_mapling_auto_map_bots_action_min_ms";
    public static final String AUTO_MAP_BOTS_ACTION_MAX_MS = "solo_mapling_auto_map_bots_action_max_ms";
    public static final String BOT_RANDOM_CHINESE_NAME = "solo_mapling_bot_random_chinese_name";
    public static final String BOT_RANDOM_SKILL_ENABLED = "solo_mapling_bot_random_skill_enabled";
    public static final String BOT_RANDOM_CHAIR_ENABLED = "solo_mapling_bot_random_chair_enabled";
    public static final String BOT_RANDOM_BODY_ENABLED = "solo_mapling_bot_random_body_enabled";
    public static final String BOT_NORMAL_EQUIPS_ENABLED = "solo_mapling_bot_normal_equips_enabled";
    public static final String BOT_FULL_EQUIPS_ENABLED = "solo_mapling_bot_full_equips_enabled";
    public static final String BOT_NX_EQUIPS_ENABLED = "solo_mapling_bot_nx_equips_enabled";
    public static final String BOT_DEFERRED_DECORATION_ENABLED = "solo_mapling_bot_deferred_decoration_enabled";
    public static final String HENESYS_BOTS_CHANGE_MAPS = "solo_mapling_henesys_bots_change_maps";
    public static final String FEATURE_FM_BOTS_ENABLED = "solo_mapling_feature_fm_bots_enabled";
    public static final String FEATURE_FM_MERCHANTS_ENABLED = "solo_mapling_feature_fm_merchants_enabled";
    public static final String FEATURE_FM_REGION_FILL_ENABLED = "solo_mapling_feature_fm_region_fill_enabled";
    public static final String FEATURE_HENESYS_CROWD_ENABLED = "solo_mapling_feature_henesys_crowd_enabled";
    public static final String FEATURE_HENESYS_MARKET_CROWD_ENABLED = "solo_mapling_feature_henesys_market_crowd_enabled";
    public static final String FEATURE_HENESYS_PARK_CROWD_ENABLED = "solo_mapling_feature_henesys_park_crowd_enabled";
    public static final String FEATURE_HENESYS_POTION_SHOP_CROWD_ENABLED = "solo_mapling_feature_henesys_potion_shop_crowd_enabled";
    public static final String FEATURE_HENESYS_GAME_ZONE_CROWD_ENABLED = "solo_mapling_feature_henesys_game_zone_crowd_enabled";
    public static final String FEATURE_GACHA_BOTS_ENABLED = "solo_mapling_feature_gacha_bots_enabled";
    public static final String FEATURE_OPQ_LOBBY_BOTS_ENABLED = "solo_mapling_feature_opq_lobby_bots_enabled";
    public static final String FEATURE_BLACKJACK_TABLES_ENABLED = "solo_mapling_feature_blackjack_tables_enabled";
    public static final String FEATURE_CASINO_NPC_ENABLED = "solo_mapling_feature_casino_npc_enabled";
    public static final String FEATURE_RPS_NPC_ENABLED = "solo_mapling_feature_rps_npc_enabled";
    public static final String FEATURE_CONVERSATION_ENABLED = "solo_mapling_feature_conversation_enabled";
    public static final String FEATURE_HOT_POTATO_ENABLED = "solo_mapling_feature_hot_potato_enabled";
    public static final String FEATURE_TUTORIAL_BOT_ENABLED = "solo_mapling_feature_tutorial_bot_enabled";
    public static final String FEATURE_PET_PARK_JQ_BOTS_ENABLED = "solo_mapling_feature_pet_park_jq_bots_enabled";
    public static final String FEATURE_PET_PARK_SOCIAL_BOTS_ENABLED = "solo_mapling_feature_pet_park_social_bots_enabled";
    public static final String FEATURE_GAME_ZONE_HOST_BOTS_ENABLED = "solo_mapling_feature_game_zone_host_bots_enabled";
    public static final String FEATURE_POTION_SHOP_DROP_GAME_ENABLED = "solo_mapling_feature_potion_shop_drop_game_enabled";
    public static final String FEATURE_SCROLL_BOTS_ENABLED = "solo_mapling_feature_scroll_bots_enabled";

    public static boolean autoEnvironmentEnabled() {
        return getBoolean(AUTO_ENVIRONMENT, false);
    }

    public static int environmentBotMax() {
        return getPositiveInt(ENVIRONMENT_BOT_MAX, 30);
    }

    public static int marketBotMax() {
        return getPositiveInt(MARKET_BOT_MAX, 10);
    }

    public static int marketShopMax() {
        return getPositiveInt(MARKET_SHOP_MAX, 10);
    }

    public static boolean autoMapBotsEnabled() {
        return getBoolean(AUTO_MAP_BOTS_ENABLED, true);
    }

    public static int autoMapBotsMin() {
        return getPositiveInt(AUTO_MAP_BOTS_MIN, 2);
    }

    public static int autoMapBotsMax() {
        return getPositiveInt(AUTO_MAP_BOTS_MAX, 4);
    }

    public static int autoMapBotsRadius() {
        return getPositiveInt(AUTO_MAP_BOTS_RADIUS, 350);
    }

    public static boolean autoMapBotsRandomPositionEnabled() {
        return getBoolean(AUTO_MAP_BOTS_RANDOM_POSITION, true);
    }

    public static boolean ambientBehaviorEnabled() {
        return getBoolean(AUTO_MAP_BOTS_AMBIENT_ENABLED, true);
    }

    public static boolean ambientMoveEnabled() {
        return getBoolean(AUTO_MAP_BOTS_MOVE_ENABLED, true);
    }

    public static boolean ambientChatEnabled() {
        return getBoolean(AUTO_MAP_BOTS_CHAT_ENABLED, true);
    }

    public static boolean ambientEmoteEnabled() {
        return getBoolean(AUTO_MAP_BOTS_EMOTE_ENABLED, true);
    }

    public static boolean ambientFacePlayerEnabled() {
        return getBoolean(AUTO_MAP_BOTS_FACE_PLAYER_ENABLED, true);
    }

    public static boolean ambientHasAnyActionEnabled() {
        return ambientMoveEnabled() || ambientChatEnabled() || ambientEmoteEnabled() || ambientFacePlayerEnabled();
    }

    public static long ambientActionMinMs() {
        return getPositiveInt(AUTO_MAP_BOTS_ACTION_MIN_MS, 2000);
    }

    public static long ambientActionMaxMs() {
        long min = ambientActionMinMs();
        long max = getPositiveInt(AUTO_MAP_BOTS_ACTION_MAX_MS, 5000);
        return Math.max(min, max);
    }

    public static boolean randomChineseNameEnabled() {
        return getBoolean(BOT_RANDOM_CHINESE_NAME, true);
    }

    public static boolean randomSkillEnabled() {
        return getBoolean(BOT_RANDOM_SKILL_ENABLED, true);
    }

    public static boolean randomChairEnabled() {
        return getBoolean(BOT_RANDOM_CHAIR_ENABLED, true);
    }

    public static boolean randomBodyEnabled() {
        return getBoolean(BOT_RANDOM_BODY_ENABLED, true);
    }

    public static boolean normalEquipsEnabled() {
        return getBoolean(BOT_NORMAL_EQUIPS_ENABLED, true);
    }

    public static boolean fullEquipsEnabled() {
        return getBoolean(BOT_FULL_EQUIPS_ENABLED, true);
    }

    public static boolean nxEquipsEnabled() {
        return getBoolean(BOT_NX_EQUIPS_ENABLED, true);
    }

    public static boolean anyOutfitFeatureEnabled() {
        return normalEquipsEnabled() || nxEquipsEnabled();
    }

    public static boolean deferredDecorationEnabled() {
        return getBoolean(BOT_DEFERRED_DECORATION_ENABLED, false);
    }

    public static boolean henesysBotsChangeMapsEnabled() {
        return getBoolean(HENESYS_BOTS_CHANGE_MAPS, false);
    }

    public static boolean fmBotsEnabled() {
        return getBoolean(FEATURE_FM_BOTS_ENABLED, true);
    }

    public static boolean fmMerchantsEnabled() {
        return getBoolean(FEATURE_FM_MERCHANTS_ENABLED, true);
    }

    public static boolean fmRegionFillEnabled() {
        return getBoolean(FEATURE_FM_REGION_FILL_ENABLED, true);
    }

    public static boolean henesysCrowdEnabled() {
        return getBoolean(FEATURE_HENESYS_CROWD_ENABLED, true);
    }

    public static boolean henesysMarketCrowdEnabled() {
        return getBoolean(FEATURE_HENESYS_MARKET_CROWD_ENABLED, true);
    }

    public static boolean henesysParkCrowdEnabled() {
        return getBoolean(FEATURE_HENESYS_PARK_CROWD_ENABLED, true);
    }

    public static boolean henesysPotionShopCrowdEnabled() {
        return getBoolean(FEATURE_HENESYS_POTION_SHOP_CROWD_ENABLED, true);
    }

    public static boolean henesysGameZoneCrowdEnabled() {
        return getBoolean(FEATURE_HENESYS_GAME_ZONE_CROWD_ENABLED, true);
    }

    public static boolean gachaBotsEnabled() {
        return getBoolean(FEATURE_GACHA_BOTS_ENABLED, true);
    }

    public static boolean opqLobbyBotsEnabled() {
        return getBoolean(FEATURE_OPQ_LOBBY_BOTS_ENABLED, true);
    }

    public static boolean blackjackTablesEnabled() {
        return getBoolean(FEATURE_BLACKJACK_TABLES_ENABLED, true);
    }

    public static boolean casinoNpcEnabled() {
        return getBoolean(FEATURE_CASINO_NPC_ENABLED, true);
    }

    public static boolean rpsNpcEnabled() {
        return getBoolean(FEATURE_RPS_NPC_ENABLED, true);
    }

    public static boolean conversationEnabled() {
        return getBoolean(FEATURE_CONVERSATION_ENABLED, true);
    }

    public static boolean hotPotatoEnabled() {
        return getBoolean(FEATURE_HOT_POTATO_ENABLED, true);
    }

    public static boolean tutorialBotEnabled() {
        return getBoolean(FEATURE_TUTORIAL_BOT_ENABLED, true);
    }

    public static boolean petParkJqBotsEnabled() {
        return getBoolean(FEATURE_PET_PARK_JQ_BOTS_ENABLED, true);
    }

    public static boolean petParkSocialBotsEnabled() {
        return getBoolean(FEATURE_PET_PARK_SOCIAL_BOTS_ENABLED, true);
    }

    public static boolean gameZoneHostBotsEnabled() {
        return getBoolean(FEATURE_GAME_ZONE_HOST_BOTS_ENABLED, true);
    }

    public static boolean potionShopDropGameEnabled() {
        return getBoolean(FEATURE_POTION_SHOP_DROP_GAME_ENABLED, true);
    }

    public static boolean scrollBotsEnabled() {
        return getBoolean(FEATURE_SCROLL_BOTS_ENABLED, true);
    }

    private static boolean getBoolean(String key, boolean defaultValue) {
        String configured = GameConfig.getServerString(key);
        return configured.isEmpty() ? defaultValue : Boolean.parseBoolean(configured);
    }

    private static int getPositiveInt(String key, int defaultValue) {
        int value = GameConfig.getServerInt(key);
        return value > 0 ? value : defaultValue;
    }
}
