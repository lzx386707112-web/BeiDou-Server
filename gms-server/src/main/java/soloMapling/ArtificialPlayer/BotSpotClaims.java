package soloMapling.ArtificialPlayer;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/BotSpotClaims.class */
public final class BotSpotClaims {
    private static final Map<Integer, Map<Integer, Map<Integer, Integer>>> CLAIMS = new ConcurrentHashMap();

    private BotSpotClaims() {
    }

    public static synchronized int claim(int mapId, int spotId, int capacity, int botId) {
        Map<Integer, Map<Integer, Integer>> bySpot = CLAIMS.computeIfAbsent(Integer.valueOf(mapId), k -> {
            return new HashMap();
        });
        Map<Integer, Integer> slots = bySpot.computeIfAbsent(Integer.valueOf(spotId), k2 -> {
            return new HashMap();
        });
        Integer existing = slots.get(Integer.valueOf(botId));
        if (existing != null) {
            return existing.intValue();
        }
        int cap = Math.max(1, capacity);
        if (slots.size() >= cap) {
            return -1;
        }
        Set<Integer> used = new HashSet<>(slots.values());
        for (int s = 0; s < cap; s++) {
            if (!used.contains(Integer.valueOf(s))) {
                slots.put(Integer.valueOf(botId), Integer.valueOf(s));
                return s;
            }
        }
        return -1;
    }

    public static synchronized void release(int mapId, int spotId, int botId) {
        Map<Integer, Integer> slots;
        Map<Integer, Map<Integer, Integer>> bySpot = CLAIMS.get(Integer.valueOf(mapId));
        if (bySpot == null || (slots = bySpot.get(Integer.valueOf(spotId))) == null) {
            return;
        }
        slots.remove(Integer.valueOf(botId));
        if (slots.isEmpty()) {
            bySpot.remove(Integer.valueOf(spotId));
        }
        if (bySpot.isEmpty()) {
            CLAIMS.remove(Integer.valueOf(mapId));
        }
    }

    public static synchronized int holders(int mapId, int spotId) {
        Map<Integer, Integer> slots;
        Map<Integer, Map<Integer, Integer>> bySpot = CLAIMS.get(Integer.valueOf(mapId));
        if (bySpot == null || (slots = bySpot.get(Integer.valueOf(spotId))) == null) {
            return 0;
        }
        return slots.size();
    }

    public static int[] section(int minX, int maxX, int slot, int capacity) {
        int k = Math.max(1, capacity);
        int s = Math.max(0, Math.min(slot, k - 1));
        int width = Math.max(0, maxX - minX);
        int x0 = minX + ((int) ((width * s) / k));
        int x1 = minX + ((int) ((width * (s + 1)) / k));
        return new int[]{x0, x1};
    }
}
