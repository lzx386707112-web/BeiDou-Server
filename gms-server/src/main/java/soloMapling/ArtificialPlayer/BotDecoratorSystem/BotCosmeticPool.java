package soloMapling.ArtificialPlayer.BotDecoratorSystem;

import soloMapling.ArtificialPlayer.BotTier;

import java.util.EnumMap;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Central registry for all cosmetic ID pools and the probability bridge
 * between bot tiers and cosmetic tiers.
 *
 * To add new hair/eye IDs: just append them to the appropriate array
 * in the pool maps below. The selection logic doesn't need to change.
 */
public class BotCosmeticPool {

    // ─── Probability bridge: bot tier → cosmetic tier selection weights ───
    // Each array is [PREMIUM, STANDARD, BASIC] and must sum to 100.

    private static final Map<BotTier, int[]> HAIR_EYE_WEIGHTS = new EnumMap<>(BotTier.class);

    static {
        //                              Premium  Standard  Basic
        HAIR_EYE_WEIGHTS.put(BotTier.S, new int[]{55,      35,      10});
        HAIR_EYE_WEIGHTS.put(BotTier.A, new int[]{40,      45,      15});
        HAIR_EYE_WEIGHTS.put(BotTier.B, new int[]{20,      55,      25});
        HAIR_EYE_WEIGHTS.put(BotTier.C, new int[]{10,      50,      40});
        HAIR_EYE_WEIGHTS.put(BotTier.D, new int[]{5,       40,      55});
    }

    // ─── Hair color variation chance by bot tier ───
    // Higher tier = more likely to have a non-default hair color

    private static final Map<BotTier, Double> HAIR_COLOR_CHANCE = new EnumMap<>(BotTier.class);

    static {
        HAIR_COLOR_CHANCE.put(BotTier.S, 0.60);
        HAIR_COLOR_CHANCE.put(BotTier.A, 0.45);
        HAIR_COLOR_CHANCE.put(BotTier.B, 0.30);
        HAIR_COLOR_CHANCE.put(BotTier.C, 0.18);
        HAIR_COLOR_CHANCE.put(BotTier.D, 0.10);
    }

    // ─── Eye color variation chance by bot tier ───

    private static final Map<BotTier, Double> EYE_COLOR_CHANCE = new EnumMap<>(BotTier.class);

    static {
        EYE_COLOR_CHANCE.put(BotTier.S, 0.55);
        EYE_COLOR_CHANCE.put(BotTier.A, 0.40);
        EYE_COLOR_CHANCE.put(BotTier.B, 0.25);
        EYE_COLOR_CHANCE.put(BotTier.C, 0.15);
        EYE_COLOR_CHANCE.put(BotTier.D, 0.08);
    }

    // ─── Wild card pools (selected via independent pre-roll, bypasses tier system) ───

    private static final double WILD_CHANCE = 0.01; // 0.5% = 1 in 200

    private static final int[] WILD_MALE_HAIR   = new int[]{46540, 46550, 47140, 48670, 48680, 48690, 42210, 42220, 42260, 42270};
    private static final int[] WILD_FEMALE_HAIR = new int[]{46540, 46550, 47140, 48670, 48680, 48690, 42210, 42220, 42260, 42270};
    private static final int[] WILD_MALE_EYES   = new int[]{20012};
    private static final int[] WILD_FEMALE_EYES = new int[]{21009};

    // ─── Male Hair Pools ───
    // Add/remove IDs as you research them. Base IDs only (color variant applied separately).

    private static final Map<CosmeticTier, int[]> MALE_HAIR = new EnumMap<>(CosmeticTier.class);

    static {
        MALE_HAIR.put(CosmeticTier.PREMIUM,  new int[]{48700, 48710, 48720, 48730, 42200, 48740, 48750, 42230, 42240, 42250, 48760, 48770});
        MALE_HAIR.put(CosmeticTier.STANDARD, new int[]{40070, 40080, 42100, 42210, 42220});
        MALE_HAIR.put(CosmeticTier.BASIC,    new int[]{40070, 40080, 42100});
    }

    // ─── Female Hair Pools ───

    private static final Map<CosmeticTier, int[]> FEMALE_HAIR = new EnumMap<>(CosmeticTier.class);

    static {
        FEMALE_HAIR.put(CosmeticTier.PREMIUM,  new int[]{46540, 46550, 47140, 48670, 48680, 48690, 48700, 48710, 48720, 48730, 42200, 48740});
        FEMALE_HAIR.put(CosmeticTier.STANDARD, new int[]{43270, 44440, 44450, 42210, 42220});
        FEMALE_HAIR.put(CosmeticTier.BASIC,    new int[]{43270, 44440, 44450});
    }

    // ─── Male Eye Pools ───

    private static final Map<CosmeticTier, int[]> MALE_EYES = new EnumMap<>(CosmeticTier.class);

    static {
        MALE_EYES.put(CosmeticTier.PREMIUM,  new int[]{20005});
        MALE_EYES.put(CosmeticTier.STANDARD, new int[]{20000, 20001, 20002});
        MALE_EYES.put(CosmeticTier.BASIC,    new int[]{20000, 20001, 20002});
    }

    // ─── Female Eye Pools ───

    private static final Map<CosmeticTier, int[]> FEMALE_EYES = new EnumMap<>(CosmeticTier.class);

    static {
        FEMALE_EYES.put(CosmeticTier.PREMIUM,  new int[]{21003, 21004});
        FEMALE_EYES.put(CosmeticTier.STANDARD, new int[]{21001, 21000, 21002});
        FEMALE_EYES.put(CosmeticTier.BASIC,    new int[]{21000, 21001, 21002});
    }

    // ─── Public selection methods ───

    /**
     * Selects a random hair ID based on the bot's gender and tier.
     * The bot tier influences which cosmetic tier pool is drawn from,
     * then a random ID is picked from that pool.
     */
    public static int selectHair(byte gender, BotTier botTier) {
        if (ThreadLocalRandom.current().nextDouble() < WILD_CHANCE) {
            int baseHair = pickRandom((gender == 1) ? WILD_FEMALE_HAIR : WILD_MALE_HAIR);
            return applyHairColor(baseHair, botTier);
        }
        Map<CosmeticTier, int[]> pool = (gender == 1) ? FEMALE_HAIR : MALE_HAIR;
        CosmeticTier cosmeticTier = rollCosmeticTier(botTier);
        int baseHair = pickRandom(pool.get(cosmeticTier));
        return applyHairColor(baseHair, botTier);
    }

    /**
     * Selects a random eye/face ID based on the bot's gender and tier.
     */
    public static int selectEyes(byte gender, BotTier botTier) {
        if (ThreadLocalRandom.current().nextDouble() < WILD_CHANCE) {
            int baseEye = pickRandom((gender == 1) ? WILD_FEMALE_EYES : WILD_MALE_EYES);
            return applyEyeColor(baseEye, botTier);
        }
        Map<CosmeticTier, int[]> pool = (gender == 1) ? FEMALE_EYES : MALE_EYES;
        CosmeticTier cosmeticTier = rollCosmeticTier(botTier);
        int baseEye = pickRandom(pool.get(cosmeticTier));
        return applyEyeColor(baseEye, botTier);
    }

    // ─── Internal helpers ───

    /**
     * Rolls a cosmetic tier based on the bot's tier using weighted probabilities.
     */
    private static CosmeticTier rollCosmeticTier(BotTier botTier) {
        int[] weights = HAIR_EYE_WEIGHTS.get(botTier);
        int roll = ThreadLocalRandom.current().nextInt(100);

        if (roll < weights[0]) {
            return CosmeticTier.PREMIUM;
        } else if (roll < weights[0] + weights[1]) {
            return CosmeticTier.STANDARD;
        } else {
            return CosmeticTier.BASIC;
        }
    }

    /**
     * Applies a random hair color variant based on bot tier.
     * Hair colors in v83 are base ID + 1 through +7.
     */
    private static int applyHairColor(int baseHair, BotTier botTier) {
        double chance = HAIR_COLOR_CHANCE.get(botTier);
        if (ThreadLocalRandom.current().nextDouble() < chance) {
            int colorOffset = ThreadLocalRandom.current().nextInt(7) + 1; // 1-7
            return baseHair + colorOffset;
        }
        return baseHair;
    }

    /**
     * Applies a random eye color variant based on bot tier.
     * Eye colors in v83 are base ID + 100 through +800 (in increments of 100).
     */
    private static int applyEyeColor(int baseEye, BotTier botTier) {
        double chance = EYE_COLOR_CHANCE.get(botTier);
        if (ThreadLocalRandom.current().nextDouble() < chance) {
            int colorOffset = (ThreadLocalRandom.current().nextInt(8) + 1) * 100; // 100-800
            return baseEye + colorOffset;
        }
        return baseEye;
    }

    private static int pickRandom(int[] array) {
        return array[ThreadLocalRandom.current().nextInt(array.length)];
    }
}
