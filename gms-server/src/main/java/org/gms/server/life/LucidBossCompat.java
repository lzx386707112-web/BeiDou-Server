package org.gms.server.life;

import org.gms.client.Character;
import org.gms.server.TimerManager;
import org.gms.server.maps.MapleMap;
import org.gms.util.PacketCreator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.Point;
import java.awt.Rectangle;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Projects the modern TMS Lucid field controller onto contracts supported by
 * the legacy client. Visual-only field mechanics are routed through MCV
 * FIELD_EFFECT markers; damage and summons remain server authoritative.
 */
public final class LucidBossCompat {
    private static final Logger log = LoggerFactory.getLogger(LucidBossCompat.class);

    private static final int PHASE_ONE = 1;
    private static final int PHASE_TWO = 2;
    private static final int PHASE_THREE = 3;
    private static final int LUCID_P1 = 8880140;
    private static final int LUCID_P2 = 8880141;
    private static final int LUCID_P3 = 8880142;
    private static final int MUSHROOM_P1 = 8880164;
    private static final int GOLEM_P1 = 8880161;
    private static final int BUTTERFLY_P1 = 8880165;
    private static final int GOLEM_P2 = 8880171;
    private static final int BUTTERFLY_P2 = 8880175;
    private static final int SEDUCE_SKILL_ID = 128;
    private static final int SEDUCE_P1_P2_LEVEL = 16;
    private static final int SEDUCE_P3_LEVEL = 10;
    private static final int CONTROL_EFFECT_COOLDOWN_MS = 60_000;
    private static final int BUTTERFLY_CAPACITY = 40;
    private static final int MAX_VISIBLE_BUTTERFLIES = 12;
    private static final int MAX_GOLEMS = 15;
    private static final int MAX_MUSHROOMS = 4;
    private static final int PHANTOM_BARRAGE_PREPARE_MS = 2400;
    private static final int PHANTOM_BARRAGE_HIT_INTERVAL_MS = 1000;
    private static final int PHANTOM_BARRAGE_HIT_COUNT = 12;
    private static final long DRAGON_BREATH_DAMAGE_MS = 6300;
    private static final long BUTTERFLY_RETURN_DURATION_MS = 3960;
    private static final long RUSH_DURATION_MS = 3000;
    private static final long RUSH_HIT_INTERVAL_MS = 100;
    private static final long CONTROLLER_TICK_MS = 250;
    private static final long FURY_LIMIT_MS = 45_000;
    private static final long FURY_FAIL_DELAY_MS = FURY_LIMIT_MS + 4320;

    private static final String EFFECT_ROOT = "customSkill/lucid/";
    private static final String DRAGON_P1_EFFECT = EFFECT_ROOT + "dragonP1VideoLayer";
    private static final String DRAGON_P2_EFFECT = EFFECT_ROOT + "dragonP2VideoLayer";
    private static final String LASER_RAIN_EFFECT = EFFECT_ROOT + "laserRainVideoLayer";
    private static final String PHANTOM_BARRAGE_EFFECT = EFFECT_ROOT + "phantomBarrageVideoLayer";
    private static final String RUSH_EFFECT = EFFECT_ROOT + "rushVideoLayer";
    private static final String FURY_EFFECT = EFFECT_ROOT + "furyVideoLayer";
    private static final String BUTTERFLY_BURST_EFFECT = EFFECT_ROOT + "butterflyBurstVideoLayer";
    private static final String BOMB_EFFECT = EFFECT_ROOT + "bombVideoLayer";
    private static final String[] STAINED_GLASS_EFFECTS = {
            EFFECT_ROOT + "stainedGlassVideoLayer",
            EFFECT_ROOT + "stainedGlass1VideoLayer",
            EFFECT_ROOT + "stainedGlass2VideoLayer",
            EFFECT_ROOT + "stainedGlass3VideoLayer",
            EFFECT_ROOT + "stainedGlass4VideoLayer",
            EFFECT_ROOT + "stainedGlass5VideoLayer",
    };

    private static final Point[] RUSH_PATH = points(new int[][]{
            {685, -510}, {45, -420}, {181, -571}, {394, -738}, {698, -792},
            {978, -746}, {1067, -587}, {1028, -403}, {732, -117}, {469, -107},
            {341, -225}, {356, -417}, {538, -576}, {804, -742}, {978, -742},
    });
    private static final int[] RUSH_SPEEDS = {
            15, 15, 20, 25, 30, 25, 20, 15, 20, 25, 20, 15, 20, 25, 20,
    };
    private static final Point RUSH_BODY_LT = new Point(-47, -135);
    private static final Point RUSH_BODY_RB = new Point(76, 14);

    private static final Rectangle[] STAINED_GLASS_AREAS = {
            new Rectangle(127, -225, 370, 200),
            new Rectangle(529, -148, 168, 200),
            new Rectangle(921, -719, 370, 200),
            new Rectangle(532, -590, 370, 200),
            new Rectangle(260, -475, 266, 200),
            new Rectangle(400, -785, 266, 200),
    };

    private static final Set<Integer> SUPPORT_MOBS = Set.of(
            MUSHROOM_P1, GOLEM_P1, BUTTERFLY_P1, GOLEM_P2, BUTTERFLY_P2);
    private static final ConcurrentMap<MapleMap, Encounter> ENCOUNTERS =
            new ConcurrentHashMap<>();

    // TMS BossLucid/Butterfly positions. The source's phase1 position 39 is
    // 17100, outside the 1960-wide field, so the legacy projection uses 1710.
    private static final Point[] PHASE_ONE_BUTTERFLY_POSITIONS = points(new int[][]{
            {120, -410}, {350, -470}, {471, -380}, {800, -290}, {960, -360},
            {1130, -415}, {1210, -401}, {1460, -453}, {1700, -357}, {1810, -439},
            {70, -300}, {300, -330}, {518, -354}, {630, -300}, {710, -334},
            {1105, -300}, {1204, -325}, {1420, -190}, {1560, -270}, {1690, -350},
            {100, -200}, {320, -280}, {530, -210}, {760, -220}, {840, -130},
            {1140, -250}, {1230, -300}, {1300, -287}, {1720, -200}, {1860, -120},
            {140, -104}, {335, -140}, {520, -80}, {640, -95}, {950, -140},
            {1100, -121}, {1140, -70}, {1310, -69}, {1560, -110}, {1710, -180},
    });
    private static final Point[] PHASE_TWO_BUTTERFLY_POSITIONS = points(new int[][]{
            {-61, -978}, {900, -300}, {203, -1042}, {400, -1014}, {595, -1014},
            {570, -1011}, {740, -922}, {924, -961}, {1107, -908}, {1398, -796},
            {388, -651}, {771, -617}, {-200, -347}, {155, -390}, {634, -327},
            {1022, -424}, {1295, -305}, {1461, -331}, {-13, -40}, {403, -227},
            {604, -288}, {683, -309}, {810, -375}, {1242, -253}, {1356, -253},
            {895, -200}, {-1, -20}, {252, 9}, {760, -80}, {939, -23},
            {1161, -34}, {1461, -18}, {1245, -219}, {1148, 42}, {555, -645},
            {210, -368}, {252, -39}, {8, -483}, {1130, -408}, {618, -1062},
    });

    private LucidBossCompat() {
    }

    public static boolean isLucidBoss(int mobId) {
        return mobId == LUCID_P1 || mobId == LUCID_P2 || mobId == LUCID_P3;
    }

    static long skillCooldownMillis(int mobId, int skillId, int level, long fallback) {
        boolean phaseOneOrTwoSeduce = (mobId == LUCID_P1 || mobId == LUCID_P2)
                && level == SEDUCE_P1_P2_LEVEL;
        boolean phaseThreeSeduce = mobId == LUCID_P3 && level == SEDUCE_P3_LEVEL;
        if (skillId == SEDUCE_SKILL_ID && (phaseOneOrTwoSeduce || phaseThreeSeduce)) {
            return CONTROL_EFFECT_COOLDOWN_MS;
        }
        return fallback;
    }

    static boolean usesAttackCooldown(int mobId, int attackPosition) {
        return (mobId == LUCID_P1 && attackPosition == 1)
                || (mobId == LUCID_P2 && attackPosition == 2);
    }

    static int attackCooldownMillis(int mobId, int attackPosition, int fallback) {
        return usesAttackCooldown(mobId, attackPosition)
                ? CONTROL_EFFECT_COOLDOWN_MS
                : fallback;
    }

    public static int butterflyIntervalMillis(int hpPercent) {
        if (hpPercent >= 90) {
            return 5000;
        }
        if (hpPercent >= 70) {
            return 4500;
        }
        if (hpPercent >= 50) {
            return 4000;
        }
        if (hpPercent >= 20) {
            return 3000;
        }
        return 2000;
    }

    public static int butterflyCreateCount(int hpPercent) {
        if (hpPercent >= 90) {
            return 5;
        }
        if (hpPercent >= 70) {
            return 7;
        }
        if (hpPercent >= 50) {
            return 10;
        }
        if (hpPercent >= 20) {
            return 15;
        }
        return 20;
    }

    public static void startPhase(MapleMap map, Monster boss, int phase) {
        if (map == null || boss == null || !isLucidBoss(boss.getId())) {
            throw new IllegalArgumentException("invalid Lucid encounter phase");
        }
        int expectedBoss = switch (phase) {
            case PHASE_ONE -> LUCID_P1;
            case PHASE_TWO -> LUCID_P2;
            case PHASE_THREE -> LUCID_P3;
            default -> -1;
        };
        if (boss.getId() != expectedBoss) {
            throw new IllegalArgumentException("Lucid phase and boss ID do not match");
        }
        if (phase == PHASE_THREE) {
            cleanupSupportMobs(map);
        }
        Encounter replacement = new Encounter(map, boss, phase);
        Encounter previous = ENCOUNTERS.put(map, replacement);
        if (previous != null) {
            previous.stop(false);
        }
        replacement.start();
    }

    public static void stop(MapleMap map) {
        if (map == null) {
            return;
        }
        Encounter encounter = ENCOUNTERS.remove(map);
        if (encounter != null) {
            encounter.stop(true);
        } else {
            cleanupSupportMobs(map);
        }
    }

    private static Point[] points(int[][] coordinates) {
        Point[] output = new Point[coordinates.length];
        for (int index = 0; index < coordinates.length; index++) {
            output[index] = new Point(coordinates[index][0], coordinates[index][1]);
        }
        return output;
    }

    private static final class Encounter implements Runnable {
        private final MapleMap map;
        private final int phase;
        private final int bossObjectId;
        private final Monster boss;
        private volatile boolean active = true;
        private volatile boolean furyFailed;
        private ScheduledFuture<?> task;
        private int butterflyGauge;
        private int butterflyPosition;
        private long nextButterfly;
        private long nextDust;
        private long nextSummon;
        private long nextDragon;
        private long nextLaser;
        private long nextShoot;
        private long nextRush;
        private long nextBomb;
        private long nextStainedGlass;
        private long nextHurdleDamage;
        private int stainedGlassIndex;
        private boolean butterflyWarningIssued;

        private Encounter(MapleMap map, Monster boss, int phase) {
            this.map = map;
            this.boss = boss;
            this.phase = phase;
            this.bossObjectId = boss.getObjectId();
            long now = System.currentTimeMillis();
            nextButterfly = now + 5000;
            nextDust = now + 9000;
            nextSummon = now + 7000;
            nextDragon = now + (phase == PHASE_ONE ? 20_000 : 28_000);
            nextLaser = now + 12_000;
            nextShoot = now + (phase == PHASE_THREE ? 8000 : 25_000);
            nextRush = now + (phase == PHASE_THREE ? 12_000 : 18_000);
            nextBomb = now + (phase == PHASE_ONE ? 12_000 : 15_000);
            nextStainedGlass = now + 10_000;
            nextHurdleDamage = now + 1000;
        }

        private void start() {
            if (phase == PHASE_THREE) {
                map.broadcastMessage(PacketCreator.showEffect(FURY_EFFECT));
                map.dropMessage(5, "[Lucid] Lucid has become enraged!");
                map.dropMessage(5, "[Lucid] The nightmare fog will close in after 45 seconds.");
                TimerManager.getInstance().schedule(() -> {
                    if (active && !furyFailed && isCurrentBossAlive()) {
                        furyFailed = true;
                        applyFullMapDamage(100, "fury-fail");
                    }
                }, FURY_FAIL_DELAY_MS);
            }
            task = TimerManager.getInstance().register(this, CONTROLLER_TICK_MS, 1000);
            log.info("[LucidCompat] started map={} phase={} boss={} oid={}",
                    map.getId(), phase, boss.getId(), bossObjectId);
        }

        @Override
        public void run() {
            if (!active) {
                return;
            }
            if (!isCurrentBossAlive()) {
                if (phase == PHASE_TWO) {
                    Monster phaseThree = map.getMonsterById(LUCID_P3);
                    if (phaseThree != null && phaseThree.isAlive()) {
                        LucidBossCompat.startPhase(map, phaseThree, PHASE_THREE);
                        return;
                    }
                }
                Encounter current = ENCOUNTERS.get(map);
                if (current == this) {
                    ENCOUNTERS.remove(map, this);
                }
                stop(false);
                return;
            }

            long now = System.currentTimeMillis();
            if (phase <= PHASE_TWO && now >= nextButterfly) {
                createButterflies(now);
            }
            if (now >= nextDust) {
                castFairyDust();
                nextDust = now + (phase == PHASE_ONE ? 12_000 : 10_000);
            }
            if (phase <= PHASE_TWO && now >= nextSummon) {
                summonNightmares();
                nextSummon = now + (phase == PHASE_ONE ? 15_000 : 18_000);
            }
            if (phase <= PHASE_TWO && now >= nextDragon) {
                castDragon();
                nextDragon = now + (phase == PHASE_ONE ? 35_000 : 38_000);
            }
            if (phase >= PHASE_TWO && now >= nextLaser) {
                castLaserRain();
                nextLaser = now + 30_000;
            }
            if (phase >= PHASE_TWO && now >= nextShoot) {
                castPhantomBarrage();
                nextShoot = now + 45_000;
            }
            if (phase >= PHASE_TWO && now >= nextRush) {
                castRush();
                nextRush = now + 20_000;
            }
            if (phase == PHASE_TWO && now >= nextStainedGlass) {
                breakStainedGlass();
                nextStainedGlass = now + 10_000;
            }
            if (phase <= PHASE_TWO && now >= nextHurdleDamage) {
                applyHurdleDamage();
                nextHurdleDamage = now + 1000;
            }
            if (now >= nextBomb) {
                castContagiousBomb();
                nextBomb = now + 25_000;
            }
        }

        private boolean isCurrentBossAlive() {
            return boss.isAlive() && boss.getMap() == map
                    && map.getMonsterByOid(bossObjectId) == boss;
        }

        private void createButterflies(long now) {
            int hpPercent = hpPercent();
            int created = butterflyCreateCount(hpPercent);
            butterflyGauge += created;
            if (!butterflyWarningIssued && butterflyGauge >= BUTTERFLY_CAPACITY / 2) {
                butterflyWarningIssued = true;
                map.dropMessage(5, "[Lucid] The dream is growing stronger. Be careful!");
            }
            Point[] positions = phase == PHASE_ONE
                    ? PHASE_ONE_BUTTERFLY_POSITIONS : PHASE_TWO_BUTTERFLY_POSITIONS;
            int butterflyId = phase == PHASE_ONE ? BUTTERFLY_P1 : BUTTERFLY_P2;
            int visible = countMobs(butterflyId);
            int toSpawn = Math.min(Math.min(created, 4), MAX_VISIBLE_BUTTERFLIES - visible);
            for (int index = 0; index < toSpawn; index++) {
                Point position = positions[butterflyPosition++ % positions.length];
                Monster butterfly = LifeFactory.getMonster(butterflyId);
                butterfly.setPosition(new Point(position));
                map.spawnMonster(butterfly);
            }
            if (butterflyGauge >= BUTTERFLY_CAPACITY) {
                butterflyGauge = 0;
                butterflyWarningIssued = false;
                map.dropMessage(5, "[Lucid] Lucid has become enraged!");
                map.broadcastMessage(PacketCreator.showEffect(BUTTERFLY_BURST_EFFECT));
                scheduleDamage(1350, 30, null, "butterfly-burst");
                TimerManager.getInstance().schedule(() -> {
                    if (active && isCurrentBossAlive()) {
                        removeMobs(Set.of(BUTTERFLY_P1, BUTTERFLY_P2));
                    }
                }, BUTTERFLY_RETURN_DURATION_MS);
            }
            nextButterfly = now + butterflyIntervalMillis(hpPercent);
        }

        private void castFairyDust() {
            Point position = boss.getPosition();
            Rectangle range = new Rectangle(position.x - 600, position.y - 500, 1200, 650);
            applyDamage(10, range, "fairy-dust");
        }

        private void summonNightmares() {
            map.dropMessage(5, "[Lucid] Lucid has summoned a powerful nightmare!");
            if (phase == PHASE_ONE && countMobs(MUSHROOM_P1) < MAX_MUSHROOMS) {
                spawnGroundMob(MUSHROOM_P1, randomGroundPoint(PHASE_ONE));
            }
            int golemId = phase == PHASE_ONE ? GOLEM_P1 : GOLEM_P2;
            int golemCount = countMobs(golemId);
            int spawnCount = Math.min(phase == PHASE_ONE ? 1 : 2, MAX_GOLEMS - golemCount);
            for (int index = 0; index < spawnCount; index++) {
                spawnGroundMob(golemId, randomGroundPoint(phase));
            }
        }

        private void castDragon() {
            map.dropMessage(5, "[Lucid] Lucid is preparing a powerful attack!");
            map.broadcastMessage(PacketCreator.showEffect(
                    phase == PHASE_ONE ? DRAGON_P1_EFFECT : DRAGON_P2_EFFECT));
            scheduleDamage(DRAGON_BREATH_DAMAGE_MS, 100, null, "dragon-breath");
        }

        private void castLaserRain() {
            map.dropMessage(5, "[Lucid] Lucid is preparing a powerful attack!");
            map.broadcastMessage(PacketCreator.showEffect(LASER_RAIN_EFFECT));
            scheduleDamage(1260, 18, null, "laser-rain-1");
            scheduleDamage(3000, 18, null, "laser-rain-2");
            TimerManager.getInstance().schedule(() -> {
                if (active && phase == PHASE_TWO && isCurrentBossAlive()
                        && countMobs(GOLEM_P2) < MAX_GOLEMS) {
                    spawnGroundMob(GOLEM_P2, randomGroundPoint(PHASE_TWO));
                }
            }, 3000);
        }

        private void castPhantomBarrage() {
            map.dropMessage(5, "[Lucid] Lucid is gathering power!");
            map.broadcastMessage(PacketCreator.showEffect(PHANTOM_BARRAGE_EFFECT));
            for (int index = 0; index < PHANTOM_BARRAGE_HIT_COUNT; index++) {
                scheduleDamage(
                        PHANTOM_BARRAGE_PREPARE_MS
                                + (long) index * PHANTOM_BARRAGE_HIT_INTERVAL_MS,
                        10, null, "phantom-barrage");
            }
        }

        private void castRush() {
            map.dropMessage(5, "[Lucid] Lucid is unleashing even greater power!");
            map.broadcastMessage(PacketCreator.showEffect(RUSH_EFFECT));
            Set<Integer> hitCharacters = ConcurrentHashMap.newKeySet();
            for (long elapsed = 0; elapsed <= RUSH_DURATION_MS;
                    elapsed += RUSH_HIT_INTERVAL_MS) {
                long collisionTime = elapsed;
                TimerManager.getInstance().schedule(() -> {
                    if (!active || !isCurrentBossAlive()) {
                        return;
                    }
                    Point position = rushPositionAt(collisionTime);
                    Rectangle body = new Rectangle(
                            position.x + RUSH_BODY_LT.x,
                            position.y + RUSH_BODY_LT.y,
                            RUSH_BODY_RB.x - RUSH_BODY_LT.x,
                            RUSH_BODY_RB.y - RUSH_BODY_LT.y);
                    for (Character character : alivePlayers()) {
                        if (body.contains(character.getPosition())
                                && hitCharacters.add(character.getId())) {
                            damageCharacter(character, 20, "rush");
                        }
                    }
                }, collisionTime);
            }
        }

        private void breakStainedGlass() {
            int index = stainedGlassIndex++ % STAINED_GLASS_AREAS.length;
            Rectangle area = STAINED_GLASS_AREAS[index];
            map.broadcastMessage(PacketCreator.showEffect(STAINED_GLASS_EFFECTS[index]));
            scheduleDamage(1260, 20, area, "stained-glass");
            TimerManager.getInstance().schedule(() -> {
                if (active && isCurrentBossAlive() && countMobs(GOLEM_P2) < MAX_GOLEMS) {
                    spawnGroundMob(GOLEM_P2, new Point(area.x + area.width / 2, area.y));
                }
            }, 3000);
        }

        private void applyHurdleDamage() {
            int golemId = phase == PHASE_ONE ? GOLEM_P1 : GOLEM_P2;
            List<Monster> golems = new ArrayList<>();
            for (Monster monster : map.getAllMonsters()) {
                if (monster.getId() == golemId && monster.isAlive()) {
                    golems.add(monster);
                }
            }
            for (Character character : alivePlayers()) {
                for (Monster golem : golems) {
                    Point position = golem.getPosition();
                    Rectangle hurdle = new Rectangle(
                            position.x - 20, position.y - 500, 40, 510);
                    if (hurdle.contains(character.getPosition())) {
                        damageCharacter(character, 20, "hurdle-area");
                        break;
                    }
                }
            }
        }

        private void castContagiousBomb() {
            List<Character> players = alivePlayers();
            if (players.isEmpty()) {
                return;
            }
            Character carrier = players.get(ThreadLocalRandom.current().nextInt(players.size()));
            carrier.dropMessage(5, "Lucid's bomb is spreading from you. Move away from the party!");
            map.broadcastMessage(PacketCreator.showEffect(BOMB_EFFECT));
            TimerManager.getInstance().schedule(() -> {
                if (!active || !isCurrentBossAlive() || !carrier.isAlive()
                        || carrier.getMap() != map) {
                    return;
                }
                Point center = carrier.getPosition();
                Rectangle range = new Rectangle(center.x - 250, center.y - 250, 500, 500);
                applyDamage(35, range, "contagious-bomb");
            }, 3000);
        }

        private void scheduleDamage(long delay, int percent, Rectangle range, String skill) {
            TimerManager.getInstance().schedule(() -> {
                if (active && isCurrentBossAlive()) {
                    applyDamage(percent, range, skill);
                }
            }, delay);
        }

        private void applyFullMapDamage(int percent, String skill) {
            applyDamage(percent, null, skill);
        }

        private void applyDamage(int percent, Rectangle range, String skill) {
            for (Character character : alivePlayers()) {
                if (range == null || range.contains(character.getPosition())) {
                    damageCharacter(character, percent, skill);
                }
            }
        }

        private void damageCharacter(Character character, int percent, String skill) {
            int damage = Math.max(1, (int) ((long) character.getMaxHp() * percent / 100));
            character.addHP(-damage);
            map.broadcastMessage(
                    character,
                    PacketCreator.damagePlayer(
                            0, boss.getId(), character.getId(), damage, 0, 0,
                            false, 0, true, boss.getObjectId(), 0, 0),
                    false);
            log.info("[LucidSkillTrace] map={} phase={} skill={} mob={} oid={} chr={} "
                            + "damagePercent={} damage={} hpAfter={}",
                    map.getId(), phase, skill, boss.getId(), boss.getObjectId(),
                    character.getName(), percent, damage, character.getHp());
        }

        private int hpPercent() {
            return Math.max(1, Math.min(100,
                    (int) Math.ceil(boss.getHp() * 100.0 / boss.getMaxHp())));
        }

        private List<Character> alivePlayers() {
            List<Character> output = new ArrayList<>();
            for (Character character : map.getAllPlayers()) {
                if (character.isAlive() && character.getMap() == map) {
                    output.add(character);
                }
            }
            return output;
        }

        private int countMobs(int mobId) {
            int count = 0;
            for (Monster monster : map.getAllMonsters()) {
                if (monster.getId() == mobId && monster.isAlive()) {
                    count++;
                }
            }
            return count;
        }

        private Point randomGroundPoint(int targetPhase) {
            int[] xPositions = targetPhase == PHASE_ONE
                    ? new int[]{220, 520, 820, 1120, 1420, 1720}
                    : new int[]{0, 250, 500, 750, 1000, 1250};
            int x = xPositions[ThreadLocalRandom.current().nextInt(xPositions.length)];
            return new Point(x, targetPhase == PHASE_ONE ? 0 : 380);
        }

        private void spawnGroundMob(int mobId, Point position) {
            Monster monster = LifeFactory.getMonster(mobId);
            map.spawnMonsterOnGroundBelow(monster, position);
        }

        private void removeMobs(Set<Integer> mobIds) {
            for (Monster monster : map.getAllMonsters()) {
                if (mobIds.contains(monster.getId())) {
                    map.killMonster(monster, null, false);
                }
            }
        }

        private void stop(boolean cleanup) {
            active = false;
            TimerManager.getInstance().stop(task);
            if (cleanup) {
                cleanupSupportMobs(map);
            }
            log.info("[LucidCompat] stopped map={} phase={} boss={} oid={}",
                    map.getId(), phase, boss.getId(), bossObjectId);
        }
    }

    static Point rushPositionAt(long elapsedMillis) {
        double[] weights = new double[RUSH_PATH.length - 1];
        double totalWeight = 0;
        for (int index = 1; index < RUSH_PATH.length; index++) {
            Point previous = RUSH_PATH[index - 1];
            Point current = RUSH_PATH[index];
            double weight = previous.distance(current) / Math.max(1, RUSH_SPEEDS[index]);
            weights[index - 1] = weight;
            totalWeight += weight;
        }
        double target = Math.max(0, Math.min(RUSH_DURATION_MS, elapsedMillis))
                * totalWeight / RUSH_DURATION_MS;
        double consumed = 0;
        for (int index = 1; index < RUSH_PATH.length; index++) {
            double segment = weights[index - 1];
            if (target <= consumed + segment || index == RUSH_PATH.length - 1) {
                double progress = segment == 0 ? 1 : (target - consumed) / segment;
                progress = Math.max(0, Math.min(1, progress));
                Point start = RUSH_PATH[index - 1];
                Point end = RUSH_PATH[index];
                return new Point(
                        (int) Math.round(start.x + (end.x - start.x) * progress),
                        (int) Math.round(start.y + (end.y - start.y) * progress));
            }
            consumed += segment;
        }
        return new Point(RUSH_PATH[RUSH_PATH.length - 1]);
    }

    private static void cleanupSupportMobs(MapleMap map) {
        for (Monster monster : map.getAllMonsters()) {
            if (SUPPORT_MOBS.contains(monster.getId())) {
                map.killMonster(monster, null, false);
            }
        }
    }
}
