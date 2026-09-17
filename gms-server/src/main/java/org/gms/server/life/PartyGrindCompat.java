package org.gms.server.life;

import java.util.concurrent.TimeUnit;

/** 消耗品 2431159「基友集合」：30 分钟组队打怪基友，不可叠加。 */
public final class PartyGrindCompat {
    public static final int ITEM_ID = 2431159;
    public static final int BOT_COUNT = 5;
    public static final int PARTY_CAP = 6;
    public static final int LEVEL_CAP = 255;
    public static final int LEVEL_JITTER = 3;
    public static final long DURATION_MS = TimeUnit.MINUTES.toMillis(30);
    public static final long WATCH_INTERVAL_MS = 1000L;

    private PartyGrindCompat() {
    }

    public static boolean canStart(boolean alreadyActive) {
        return !alreadyActive;
    }

    public static boolean hasParty(boolean inParty) {
        return inParty;
    }

    public static int freeSlots(int partySize) {
        return Math.max(0, PARTY_CAP - Math.max(0, partySize));
    }

    public static boolean canSummonFive(int partySize) {
        return partySize >= 1 && freeSlots(partySize) >= BOT_COUNT;
    }

    public static long durationMillis() {
        return DURATION_MS;
    }

    public static int durationMinutes() {
        return (int) TimeUnit.MILLISECONDS.toMinutes(DURATION_MS);
    }

    public static boolean isActive(long nowMillis, long expireAtMillis) {
        return expireAtMillis > nowMillis;
    }

    /** Leader level plus a -3..3 offset, clamped to 1..255. */
    public static int companionLevel(int leaderLevel, int offset) {
        int jitter = Math.max(-LEVEL_JITTER, Math.min(LEVEL_JITTER, offset));
        return Math.max(1, Math.min(LEVEL_CAP, leaderLevel + jitter));
    }

    /** Round-robin floor slot so 5 bots spread across N floors in one assignment. */
    public static int floorIndex(int botIndex, int floorCount) {
        if (floorCount <= 0) {
            return 0;
        }
        return Math.floorMod(botIndex, floorCount);
    }
}
