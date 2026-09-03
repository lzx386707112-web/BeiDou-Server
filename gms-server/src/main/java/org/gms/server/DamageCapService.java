package org.gms.server;

import org.gms.client.Character;
import org.gms.util.Randomizer;

import java.util.Map;

/** Server-authoritative per-character damage-cap progression. */
public final class DamageCapService {
    public static final int INITIAL_CAP = 19_999_999;
    public static final int MAX_CAP = Integer.MAX_VALUE;

    private static final Map<Integer, Integer> STONE_INCREMENTS = Map.of(
            2431152, 300_000,
            2431153, 500_000,
            2431154, 2_000_000,
            2431155, 10_000_000,
            2431156, 100_000_000,
            2431157, 500_000_000
    );

    private DamageCapService() {
    }

    public record BreakthroughResult(boolean success, boolean changed,
                                     int previousCap, int currentCap, int increment) {
    }

    public static boolean isBreakthroughStone(int itemId) {
        return STONE_INCREMENTS.containsKey(itemId);
    }

    public static int incrementForStone(int itemId) {
        return STONE_INCREMENTS.getOrDefault(itemId, 0);
    }

    public static BreakthroughResult attempt(Character player, int itemId) {
        int increment = incrementForStone(itemId);
        if (player == null || increment == 0) {
            throw new IllegalArgumentException("invalid damage-cap breakthrough request");
        }
        BreakthroughResult result = resolve(player.getDamageCap(), increment, Randomizer.nextBoolean());
        if (result.changed()) {
            player.setDamageCap(result.currentCap());
        }
        return result;
    }

    static BreakthroughResult resolve(int currentCap, int increment, boolean success) {
        int normalizedCap = normalizeCap(currentCap);
        if (!success || (long) normalizedCap + increment > MAX_CAP) {
            return new BreakthroughResult(success, false, normalizedCap, normalizedCap, increment);
        }
        int newCap = normalizedCap + increment;
        return new BreakthroughResult(true, true, normalizedCap, newCap, increment);
    }

    public static int normalizeCap(Integer cap) {
        if (cap == null || cap < INITIAL_CAP) {
            return INITIAL_CAP;
        }
        return Math.min(cap, MAX_CAP);
    }

    public static int capDamage(Character player, int damage) {
        return capDamage(player.getDamageCap(), damage);
    }

    static int capDamage(int damageCap, int damage) {
        if (damage <= 0) {
            return Math.max(0, damage);
        }
        return Math.min(damage, normalizeCap(damageCap));
    }

    public static int decodeClientDamage(int damage) {
        if (damage >= 0) {
            return damage;
        }
        return (int) Math.min(MAX_CAP, (long) damage + (long) MAX_CAP + 1L);
    }

    public static int capEncodedClientDamage(Character player, int damage) {
        return capEncodedClientDamage(player.getDamageCap(), damage);
    }

    static int capEncodedClientDamage(int damageCap, int damage) {
        boolean encoded = damage < 0;
        int capped = capDamage(damageCap, decodeClientDamage(damage));
        if (!encoded) {
            return capped;
        }
        return (int) ((long) capped - (long) MAX_CAP - 1L);
    }
}
