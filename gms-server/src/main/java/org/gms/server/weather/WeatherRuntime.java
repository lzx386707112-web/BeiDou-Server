package org.gms.server.weather;

import java.util.EnumMap;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

public final class WeatherRuntime {
    public static final int MINUTES_PER_DAY = 1440;
    public static final byte FLAG_SNAP = 0x01;
    public static final byte FLAG_FROZEN = 0x02;
    public static final byte FLAG_DISABLED = 0x08;

    private static final AtomicReference<WeatherConfigSnapshot> CONFIG =
            new AtomicReference<>(WeatherConfigSnapshot.defaults());
    private static final AtomicLong NEXT_ROLL_AT = new AtomicLong(0L);
    private static final Object STATE_LOCK = new Object();
    private static final Map<WeatherRegion, WeatherProfile> SKY = new EnumMap<>(WeatherRegion.class);
    private static final Map<WeatherRegion, Long> SKY_SINCE = new EnumMap<>(WeatherRegion.class);
    private static final Map<WeatherRegion, Integer> SKY_TOKEN = new EnumMap<>(WeatherRegion.class);
    private static final Map<WeatherRegion, Long> RAINBOW_UNTIL = new EnumMap<>(WeatherRegion.class);
    private static volatile WeatherProfile weatherOverride;
    private static volatile int timeOverrideMinute = -1;
    private static volatile long overrideUntil;

    static {
        long now = System.currentTimeMillis();
        for (WeatherRegion region : WeatherRegion.values()) {
            WeatherProfile initial = region.forcedProfile() == null
                    ? WeatherProfile.CLEAR : region.forcedProfile();
            SKY.put(region, initial);
            SKY_SINCE.put(region, now);
            SKY_TOKEN.put(region, ThreadLocalRandom.current().nextInt());
            RAINBOW_UNTIL.put(region, 0L);
        }
    }

    private WeatherRuntime() {
    }

    public static WeatherConfigSnapshot config() { return CONFIG.get(); }

    public static void replaceConfig(WeatherConfigSnapshot snapshot) {
        WeatherConfigSnapshot previousSnapshot = CONFIG.getAndSet(snapshot);
        NEXT_ROLL_AT.set(0L);
        synchronized (STATE_LOCK) {
            long now = System.currentTimeMillis();
            for (WeatherRegion region : WeatherRegion.values()) {
                WeatherProfile forced = snapshot.region(region).forcedProfile();
                WeatherProfile previous = effectiveSky(region, previousSnapshot);
                if (forced != null) {
                    SKY.put(region, forced);
                }
                WeatherProfile next = effectiveSky(region, snapshot);
                if (weatherOverride == null && previous != next) {
                    recordTransition(region, previous, next, now);
                }
            }
        }
    }

    public static int minuteOfDay() {
        expireOverride();
        if (timeOverrideMinute >= 0) return timeOverrideMinute;
        long dayLength = CONFIG.get().dayLengthMs();
        long intoDay = Math.floorMod(System.currentTimeMillis(), dayLength);
        return (int) ((intoDay * MINUTES_PER_DAY) / dayLength);
    }

    public static int msPerGameMinute() {
        return (int) Math.max(1L, CONFIG.get().dayLengthMs() / MINUTES_PER_DAY);
    }

    public static float nightLevel() {
        int minute = minuteOfDay();
        if (minute < 300 || minute >= 1140) return 1f;
        if (minute < 420) return 1f - (minute - 300) / 120f;
        if (minute < 1020) return 0f;
        return (minute - 1020) / 120f;
    }

    public static boolean isTimeFrozen() {
        expireOverride();
        return timeOverrideMinute >= 0;
    }

    public static boolean isWeatherOverridden() {
        expireOverride();
        return weatherOverride != null;
    }

    public static WeatherProfile overrideProfile() {
        expireOverride();
        return weatherOverride;
    }

    public static long overrideRemainingSec() {
        expireOverride();
        return overrideUntil == 0L ? 0L : Math.max(0L, (overrideUntil - System.currentTimeMillis()) / 1000L);
    }

    public static void override(WeatherProfile profile, Integer minute, long durationMs) {
        if (profile == null && minute == null) {
            throw new IllegalArgumentException("至少需要指定天气或时间");
        }
        expireOverride();
        synchronized (STATE_LOCK) {
            long now = System.currentTimeMillis();
            WeatherProfile previousOverride = weatherOverride;
            if (profile != null) {
                for (WeatherRegion region : WeatherRegion.values()) {
                    WeatherProfile previous = previousOverride == null
                            ? effectiveSky(region, CONFIG.get()) : previousOverride;
                    if (previous != profile) {
                        recordTransition(region, previous, profile, now);
                    }
                }
            } else if (previousOverride != null) {
                restoreAutomaticSky(previousOverride, now);
            }
            weatherOverride = profile;
            timeOverrideMinute = minute == null ? -1 : minute;
            overrideUntil = now + durationMs;
        }
    }

    public static void clearOverride() {
        synchronized (STATE_LOCK) {
            WeatherProfile previous = weatherOverride;
            if (previous != null) {
                restoreAutomaticSky(previous, System.currentTimeMillis());
            }
            weatherOverride = null;
            timeOverrideMinute = -1;
            overrideUntil = 0L;
        }
        NEXT_ROLL_AT.set(0L);
    }

    public static boolean rollIfDue() {
        expireOverride();
        WeatherConfigSnapshot snapshot = CONFIG.get();
        if (!snapshot.enabled() || weatherOverride != null) return false;
        long now = System.currentTimeMillis();
        long due = NEXT_ROLL_AT.get();
        if (due > now || !NEXT_ROLL_AT.compareAndSet(due, now + snapshot.changeIntervalMs())) {
            return false;
        }
        synchronized (STATE_LOCK) {
            for (WeatherRegion region : WeatherRegion.values()) {
                WeatherConfigSnapshot.RegionConfig config = snapshot.region(region);
                setSky(region, config.forcedProfile() == null
                        ? pick(config.weights()) : config.forcedProfile(), now);
            }
        }
        return true;
    }

    public static WeatherProfile skyForRegion(WeatherRegion region) {
        expireOverride();
        if (!CONFIG.get().enabled()) return WeatherProfile.CLEAR;
        if (weatherOverride != null) return weatherOverride;
        WeatherProfile forced = CONFIG.get().region(region).forcedProfile();
        if (forced != null) return forced;
        synchronized (STATE_LOCK) {
            return SKY.getOrDefault(region, WeatherProfile.CLEAR);
        }
    }

    public static long skyElapsedMs(WeatherRegion region) {
        synchronized (STATE_LOCK) {
            return Math.max(0L, System.currentTimeMillis() - SKY_SINCE.getOrDefault(region, System.currentTimeMillis()));
        }
    }

    public static int skyToken(WeatherRegion region) {
        synchronized (STATE_LOCK) {
            return SKY_TOKEN.getOrDefault(region, 0);
        }
    }

    public static int rainbowSecsLeft(WeatherRegion region) {
        synchronized (STATE_LOCK) {
            return (int) Math.min(Short.MAX_VALUE,
                    Math.max(0L, (RAINBOW_UNTIL.getOrDefault(region, 0L) - System.currentTimeMillis()) / 1000L));
        }
    }

    public static long nextRollInSec() {
        return Math.max(0L, (NEXT_ROLL_AT.get() - System.currentTimeMillis()) / 1000L);
    }

    private static void expireOverride() {
        if (overrideUntil > 0L && overrideUntil <= System.currentTimeMillis()) clearOverride();
    }

    private static WeatherProfile pick(double[] weights) {
        double total = 0d;
        for (double weight : weights) total += Math.max(0d, weight);
        if (total <= 0d) return WeatherProfile.CLEAR;
        double cursor = ThreadLocalRandom.current().nextDouble(total);
        WeatherProfile[] profiles = WeatherProfile.values();
        for (int i = 0; i < profiles.length; i++) {
            cursor -= Math.max(0d, weights[i]);
            if (cursor < 0d) return profiles[i];
        }
        return WeatherProfile.CLEAR;
    }

    private static void setSky(WeatherRegion region, WeatherProfile profile, long now) {
        WeatherProfile previous = SKY.put(region, profile);
        if (previous != profile) {
            recordTransition(region, previous, profile, now);
        }
    }

    private static WeatherProfile effectiveSky(WeatherRegion region,
                                                WeatherConfigSnapshot snapshot) {
        if (weatherOverride != null) return weatherOverride;
        WeatherProfile forced = snapshot.region(region).forcedProfile();
        return forced == null ? SKY.getOrDefault(region, WeatherProfile.CLEAR) : forced;
    }

    private static void restoreAutomaticSky(WeatherProfile previous, long now) {
        WeatherConfigSnapshot snapshot = CONFIG.get();
        for (WeatherRegion region : WeatherRegion.values()) {
            WeatherProfile next = effectiveSkyWithoutOverride(region, snapshot);
            if (previous != next) {
                recordTransition(region, previous, next, now);
            }
        }
    }

    private static WeatherProfile effectiveSkyWithoutOverride(WeatherRegion region,
                                                               WeatherConfigSnapshot snapshot) {
        WeatherProfile forced = snapshot.region(region).forcedProfile();
        return forced == null ? SKY.getOrDefault(region, WeatherProfile.CLEAR) : forced;
    }

    private static void recordTransition(WeatherRegion region, WeatherProfile previous,
                                         WeatherProfile next, long now) {
        SKY_SINCE.put(region, now);
        SKY_TOKEN.put(region, ThreadLocalRandom.current().nextInt());
        if (isWet(previous) && !isWet(next)) {
            RAINBOW_UNTIL.put(region, now + CONFIG.get().rainbowDurationSec() * 1000L);
        } else {
            RAINBOW_UNTIL.put(region, 0L);
        }
    }

    private static boolean isWet(WeatherProfile profile) {
        return profile == WeatherProfile.RAIN || profile == WeatherProfile.STORM;
    }
}
