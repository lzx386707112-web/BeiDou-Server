package org.gms.server.life;

import org.gms.client.Character;
import org.gms.constants.game.CharacterStance;
import org.gms.constants.id.MobId;
import org.gms.server.TimerManager;
import org.gms.server.maps.AbstractAnimatedMapObject;
import org.gms.server.maps.FootholdTree;
import org.gms.server.maps.MapleMap;
import org.gms.util.PacketCreator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.Point;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 戴米安仅保留 skill2 光球。合同与方法注释以 skill
 * {@code beidou-damien-boss} 为准。
 *
 * <p>本体 skill1–4 走投影 MobSkill 100 / 101 / 123 / 128，由
 * {@link org.gms.net.server.channel.handlers.MoveLifeHandler} 通用 apply。
 * 本类不发 MCV、不刻印、不改 TAKE_DAMAGE。二阶段飞剑/暗影球走 8880114/8880113，
 * 不要召唤 8880102。
 */
public final class DamienBossCompat {
    private static final Logger log = LoggerFactory.getLogger(DamienBossCompat.class);

    /** 一阶段本体；只有它放 skill2 光球。 */
    public static final int PHASE_ONE = 8880110;
    /** 二阶段本体；只走投影 MobSkill。 */
    public static final int PHASE_TWO = 8880111;
    /** 禁止召唤的 ID；MapleMap 会拦截。 */
    public static final int SKILL2_BANNED_MOB = MobId.DAMIEN_CRASH_ON_SUMMON;
    /**
     * 光球射手：旧端不能从 skill 姿势出弹，所以投影到 {@code 8880112}
     *（8880165 的 type=2 ball 合同 + TMS 8880101 attack3/info/ball 像素）。
     * {@code setPosition} 后 {@code spawnMonster}，不搬飞体。不要用 8880102，也不召唤 8880101。
     */
    public static final int SKILL2_ORB_MOB = MobId.DAMIEN_SKILL2_ORB;
    public static final int SHADOW_ORB_MOB = MobId.DAMIEN_SHADOW_ORB;
    public static final int FLYING_SWORD_MOB = MobId.DAMIEN_FLYING_SWORD;
    /** attack3 两排各 4 颗，共两波，对齐图 1。 */
    public static final int ATTACK3_ROWS = 2;
    public static final int ATTACK3_PER_ROW = 4;
    public static final int ATTACK3_WAVES = 2;
    public static final int ATTACK3_START_MS = 0;
    public static final int ATTACK3_WAVE_MS = 900;
    public static final int ATTACK3_SPREAD_X = 420;
    public static final int ATTACK3_UPPER_OFFSET_Y = 120;
    public static final int ATTACK3_COL_STAGGER_MS = 80;
    public static final int ATTACK3_ROW_STAGGER_MS = 50;
    public static final int ATTACK3_CAST_COOLDOWN_MS = 2200;
    public static final int HOVER_OFFSET_Y = 260;
    public static final int PHASE2_ORB_COUNT = 2;
    public static final int FLY_STEP = 10;
    public static final int SWORD_COUNT = 2;
    /** 飞剑资源与轨迹先留着，进图不刷，以后再开。 */
    public static final boolean SPAWN_FLYING_SWORDS = false;
    public static final int SWORD_AMP_Y = 240;
    public static final int SWORD_AMP_X_MIN = 560;
    public static final double SWORD_PATH_STEP = 0.04;
    public static final int FLY_MOVE_DURATION_MS = 70;
    /** 飞剑比漩涡晚刷，进图崩时可分辨是 8880113 还是 8880114。 */
    public static final int SWORD_SPAWN_DELAY_MS = 2000;
    /** 飞天后同时发出的扇形球数（原先 4，减半以免铺满地面）。 */
    public static final int SKILL2_FAN_COUNT = 2;
    /** 扇形之后交错发出的追人单球数（原先 8，减半）。 */
    public static final int SKILL2_SINGLE_COUNT = 4;
    /** 金火弹命中改为客户端 TakeDamage + {@code fixDamR}，不要服务端抢先结算。 */
    public static final int SKILL2_ORB_DAMAGE_PERCENT = 20;
    /** 与玩家脚底距离判定，单位像素。仅规划落点，不再做服务端扫到即伤。 */
    public static final int SKILL2_ORB_HIT_RADIUS = 56;
    /** 扇形球飞行时长（毫秒）。 */
    public static final int SKILL2_FAN_DURATION_MS = 1100;
    /** 扇形水平/下落幅度（像素）。 */
    public static final int SKILL2_FAN_TRAVEL = 480;
    /**
     * 对齐 skill2 帧 0–30（约 31×90ms）。到点后才出球，避免地面闪球。
     */
    public static final int SKILL2_AIRBORNE_MS = 2790;
    /**
     * 天上姿势 origin y≈661，stand origin y≈146，差值约 520。
     * 起点 = 本体.y − 本值。
     */
    public static final int SKILL2_SKY_OFFSET_Y = 520;
    /** 单球之间的出发间隔（毫秒）。第 n 颗 delay = n × 本值。 */
    public static final int SKILL2_SINGLE_STAGGER_MS = 180;
    /**
     * skill2 飞天时的地面熔岩带。TMS 是场景技能，旧端走 Map/Effect FIELD_EFFECT，
     * 不要 MCV、不要当地图 Back 铺。
     */
    /**
     * skill2 曾广播 customBossDemian/groundBurst。那是把 areaWarning 拉满屏幕，
     * 会变成压扁的预警脸。不要再 FIELD_EFFECT。
     */
    public static final String SKILL2_GROUND_EFFECT = "customBossDemian/groundBurst";
    /** 场地插值与碰撞轮询间隔。要短于移动 duration，客户端才能把位移连成线。 */
    private static final long TICK_MS = 50;

    private static final ConcurrentMap<MapleMap, Skill2OrbField> SKILL2_FIELDS =
            new ConcurrentHashMap<>();
    private static final ConcurrentMap<MapleMap, PhaseTwoField> PHASE2_FIELDS =
            new ConcurrentHashMap<>();

    private DamienBossCompat() {
    }

    /**
     * @param mobId 怪物模板 ID
     * @return 是否为一/二阶段戴米安本体
     */
    public static boolean isDamien(int mobId) {
        return mobId == PHASE_ONE || mobId == PHASE_TWO;
    }

    /**
     * 拒绝 stand/1x1 残留攻击：它们的 {@code attackAfter=30} 会在特效前立刻 TakeDamage。
     *
     * @param mobId 本体模板
     * @param attackIndex 0-based {@code attack1...}
     */
    public static boolean allowClientAttack(int mobId, int attackIndex) {
        if (mobId == PHASE_ONE) {
            return attackIndex == 0 || attackIndex == 2;
        }
        if (mobId == PHASE_TWO) {
            return attackIndex == 0 || attackIndex == 2 || attackIndex == 6;
        }
        return true;
    }

    /**
     * 疾病/效果对齐画面冲击帧，不要用整段 pose（偏晚）或 stub 的 0ms（偏早）。
     *
     * @param mobId 本体模板
     * @param skillActionIndex 0-based skill1...
     * @param animationTime LifeFactory 对整段 skill 帧 delay 求和
     */
    public static int skillEffectDelayMs(int mobId, int skillActionIndex, int animationTime) {
        if (mobId == PHASE_ONE) {
            if (skillActionIndex == 2) {
                return 3240;
            }
            if (skillActionIndex == 3) {
                return 2610;
            }
        } else if (mobId == PHASE_TWO) {
            if (skillActionIndex == 2) {
                return 3060;
            }
        }
        return Math.max(0, animationTime);
    }

    /**
     * 旧 DamienBattle.js 的 playerEntry / changedMap 仍会调。Encounter 已删，空实现以免 Graal Unknown identifier。
     *
     * @param chr 进图玩家；可 null
     */
    public static void onPlayerEnter(Character chr) {
    }

    /**
     * 玩家已在图上之后刷 8880113、2 个贴地 8880112。8880114 先不刷。不要刷 8880102。
     * 不发 walk 的 MOVE_MONSTER：这些怪只有 fly，单独召唤不崩、进图立刻走步会崩。
     *
     * @param map 副本图
     * @param boss 二阶段本体
     * @param phase 仅 phase=2 生效
     */
    public static void startPhase(MapleMap map, Monster boss, int phase) {
        if (map == null || boss == null || phase != 2 || boss.getId() != PHASE_TWO) {
            return;
        }
        PhaseTwoField field = PHASE2_FIELDS.computeIfAbsent(map, PhaseTwoField::new);
        field.boot(boss);
    }

    /**
     * 清掉该图未飞完的服务端光球判定（换图、清场、dispose）。
     *
     * @param map 副本图；null 忽略
     */
    public static void stop(MapleMap map) {
        if (map == null) {
            return;
        }
        Skill2OrbField field = SKILL2_FIELDS.remove(map);
        if (field != null) {
            field.stop();
        }
        PhaseTwoField phaseTwo = PHASE2_FIELDS.remove(map);
        if (phaseTwo != null) {
            phaseTwo.stop();
        }
    }

    /**
     * MOVE_LIFE 识别到一阶段 skill2（action 下标 1）时排队出球。
     * 延迟只用 {@link #SKILL2_AIRBORNE_MS}，不看 MobSkill 101 动画时长。
     *
     * @param monster 正在施法的本体；非 8880110 忽略
     */
    public static void onSkill2Cast(Monster monster) {
        if (monster == null || monster.getMap() == null || monster.getId() != PHASE_ONE) {
            return;
        }
        Skill2OrbField field = SKILL2_FIELDS.computeIfAbsent(monster.getMap(), Skill2OrbField::new);
        field.cast(monster);
    }

    /**
     * 二阶段 attack3：本体 IMG 的 type=2 仍飞出 1 颗弹。场地金球只在 startPhase 刷 2 个，这里不再加刷。
     */
    public static void onAttack3Cast(Monster monster) {
        if (monster == null || monster.getMap() == null || monster.getId() != PHASE_TWO) {
            return;
        }
        PhaseTwoField field = PHASE2_FIELDS.computeIfAbsent(monster.getMap(), PhaseTwoField::new);
        field.castAttack3(monster);
    }

    /**
     * @param wave {@code fan} 同时出发；{@code single} 交错追人
     * @param start 天上起点
     * @param control 二次贝塞尔控制点
     * @param end 落点（单球运行时会被锁定玩家刷新）
     * @param durationMs 飞行时长
     * @param delayMs 相对飞天结束时刻的额外等待
     */
    public record Skill2OrbPlan(String wave, Point start, Point control, Point end, long durationMs, long delayMs) {
    }

    /**
     * 生成 2 扇形 + 4 交错单球。无地图副作用，可供单测固定种子。
     *
     * @param sky 天上原点（本体 x，y − {@link #SKILL2_SKY_OFFSET_Y}）
     * @param ground 扇形 y 下限与单球瞄准参考（优先玩家脚底）
     * @param random 单球抖动与时长
     */
    public static List<Skill2OrbPlan> planSkill2Orbs(Point sky, Point ground, Random random) {
        List<Skill2OrbPlan> plans = new ArrayList<>();
        Point origin = new Point(sky);
        double[] angles = {-0.55, 0.55};
        if (angles.length != SKILL2_FAN_COUNT) {
            throw new IllegalStateException("skill2 fan count must stay at " + SKILL2_FAN_COUNT);
        }
        for (double angle : angles) {
            int dx = (int) Math.round(Math.sin(angle) * SKILL2_FAN_TRAVEL);
            int dy = (int) Math.round(Math.abs(Math.cos(angle)) * SKILL2_FAN_TRAVEL);
            int hoverY = ground.y;
            Point end = new Point(origin.x + dx, hoverY);
            Point control = new Point((origin.x + end.x) / 2, (origin.y + end.y) / 2);
            plans.add(new Skill2OrbPlan("fan", new Point(origin), control, end, SKILL2_FAN_DURATION_MS, 0));
        }
        for (int index = 0; index < SKILL2_SINGLE_COUNT; index++) {
            int offsetX = random.nextInt(321) - 160;
            Point start = new Point(origin.x + offsetX, origin.y + random.nextInt(81) - 40);
            Point end = new Point(ground.x + random.nextInt(241) - 120, ground.y);
            int sway = random.nextInt(221) - 110;
            Point control = new Point((start.x + end.x) / 2 + sway, start.y + (end.y - start.y) / 3);
            long duration = 800 + random.nextInt(401);
            plans.add(new Skill2OrbPlan("single", start, control, end, duration,
                    (long) SKILL2_SINGLE_STAGGER_MS * index));
        }
        return plans;
    }

    /**
     * 图 1：两排火球。上排在本体上方，下排贴地，两波连发。
     */
    public record Attack3BallPlan(Point start, long delayMs) {
    }

    public static List<Attack3BallPlan> planAttack3Balls(Point origin, Point ground) {
        List<Attack3BallPlan> plans = new ArrayList<>();
        int[] rowY = {origin.y - HOVER_OFFSET_Y - 40, origin.y - HOVER_OFFSET_Y + 40};
        if (rowY.length != ATTACK3_ROWS) {
            throw new IllegalStateException("attack3 row count must stay at " + ATTACK3_ROWS);
        }
        int step = ATTACK3_PER_ROW <= 1 ? 0 : (2 * ATTACK3_SPREAD_X) / (ATTACK3_PER_ROW - 1);
        for (int wave = 0; wave < ATTACK3_WAVES; wave++) {
            int waveShift = wave * 50;
            for (int row = 0; row < ATTACK3_ROWS; row++) {
                for (int index = 0; index < ATTACK3_PER_ROW; index++) {
                    int x = origin.x - ATTACK3_SPREAD_X + index * step + waveShift;
                    long delay = (long) ATTACK3_START_MS
                            + (long) wave * ATTACK3_WAVE_MS
                            + (long) row * ATTACK3_ROW_STAGGER_MS
                            + (long) index * ATTACK3_COL_STAGGER_MS;
                    plans.add(new Attack3BallPlan(new Point(x, rowY[row]), delay));
                }
            }
        }
        return plans;
    }

    /**
     * @param t 进度，会钳到 [0,1]
     */
    public static Point bezier(Point start, Point control, Point end, double t) {
        double clamped = Math.max(0, Math.min(1, t));
        double remain = 1 - clamped;
        return new Point(
                (int) Math.round(remain * remain * start.x + 2 * remain * clamped * control.x + clamped * clamped * end.x),
                (int) Math.round(remain * remain * start.y + 2 * remain * clamped * control.y + clamped * clamped * end.y));
    }

    /**
     * 飞剑轨迹。0 横向 8 字，1 反向 8 字，2 椭圆。t 为弧度。
     */
    public static Point swordPathPoint(int pattern, double t, Point center, int ampX, int ampY) {
        double x;
        double y;
        int kind = Math.floorMod(pattern, 3);
        if (kind == 0) {
            x = center.x + ampX * Math.sin(t);
            y = center.y + ampY * Math.sin(t) * Math.cos(t);
        } else if (kind == 1) {
            x = center.x + ampX * Math.sin(t + Math.PI);
            y = center.y + ampY * Math.sin(t + Math.PI) * Math.cos(t + Math.PI);
        } else {
            x = center.x + ampX * Math.cos(t * 0.85);
            y = center.y + ampY * Math.sin(t * 1.7);
        }
        return new Point((int) Math.round(x), (int) Math.round(y));
    }

    /**
     * 飞剑朝向：水平用 stand 左右，斜向/垂直用 jump（8880114 的 jump 是 45° 剑身）。
     * 不要 walk 2/3。
     */
    public static int swordFacingStance(int dx, int dy, boolean facingLeftFallback) {
        if (dx == 0 && dy == 0) {
            return facingLeftFallback ? CharacterStance.STAND_LEFT_STANCE : CharacterStance.STAND_RIGHT_STANCE;
        }
        double angle = Math.atan2(-dy, dx);
        int sector = Math.floorMod((int) Math.round(angle / (Math.PI / 4.0)), 8);
        boolean left = sector >= 3 && sector <= 5;
        boolean diagonalOrVertical = sector != 0 && sector != 4;
        if (diagonalOrVertical) {
            return left ? CharacterStance.JUMP_LEFT_STANCE : CharacterStance.JUMP_RIGHT_STANCE;
        }
        return left ? CharacterStance.STAND_LEFT_STANCE : CharacterStance.STAND_RIGHT_STANCE;
    }

    /** fly 怪用站立左右姿态，不要 walk 2/3（旧端会去找 move 动作然后崩）。 */
    private static void flyShift(MapleMap map, Monster mob, Point next) {
        flyShift(map, mob, next, next.x - mob.getPosition().x, next.y - mob.getPosition().y, false);
    }

    private static void flyShift(MapleMap map, Monster mob, Point next, int faceDx, int faceDy, boolean sword) {
        Point from = new Point(mob.getPosition());
        int stance = sword
                ? swordFacingStance(faceDx, faceDy, mob.isFacingLeft())
                : (faceDx == 0
                ? (mob.isFacingLeft() ? CharacterStance.STAND_LEFT_STANCE : CharacterStance.STAND_RIGHT_STANCE)
                : (faceDx < 0 ? CharacterStance.STAND_LEFT_STANCE : CharacterStance.STAND_RIGHT_STANCE));
        int duration = FLY_MOVE_DURATION_MS;
        int vx = duration <= 0 ? 0 : (next.x - from.x) * 1000 / duration;
        int vy = duration <= 0 ? 0 : (next.y - from.y) * 1000 / duration;
        mob.setStance(stance);
        map.moveMonster(mob, next);
        map.broadcastMessage(PacketCreator.moveMonster(
                mob.getObjectId(),
                false,
                -1,
                0,
                0,
                0,
                from,
                mob.getAbsoluteMovement(next.x, next.y, 0, stance, duration, vx, vy),
                AbstractAnimatedMapObject.IDLE_MOVEMENT_PACKET_LENGTH));
    }

    /** 每图一份：只刷 8880112。扣血走客户端弹道 TakeDamage + fixDamR，不要贝塞尔抢先结算。 */
    private static final class Skill2OrbField implements Runnable {
        private final MapleMap map;
        private final List<Integer> shooterOids = new ArrayList<>();
        private final List<ScheduledFuture<?>> spawnTasks = new ArrayList<>();
        private Monster boss;
        private ScheduledFuture<?> task;
        private volatile boolean active = true;
        private int hoverY;

        private Skill2OrbField(MapleMap map) {
            this.map = map;
        }

        private void cast(Monster monster) {
            this.boss = monster;
            Character focus = monster.getController();
            if (focus == null || !focus.isAlive() || focus.getMap() != map) {
                List<Character> players = new ArrayList<>(map.getCharacters());
                focus = players.isEmpty() ? null : players.get(0);
            }
            Point ground = focus != null ? new Point(focus.getPosition()) : new Point(monster.getPosition());
            Point sky = new Point(monster.getPosition().x, monster.getPosition().y - SKILL2_SKY_OFFSET_Y);
            long airborne = System.currentTimeMillis() + SKILL2_AIRBORNE_MS;
            List<Skill2OrbPlan> plans = planSkill2Orbs(sky, ground, ThreadLocalRandom.current());
            for (Skill2OrbPlan plan : plans) {
                queueShooter(plan.start(), airborne + plan.delayMs());
            }
            this.hoverY = ground.y;
            if (task == null || task.isCancelled()) {
                task = TimerManager.getInstance().register(this, TICK_MS, TICK_MS);
            }
            log.info("[DamienCompat] skill2 orbs queued map={} count={} visual=8880112 groundY={} clientHit=1",
                    map.getId(), plans.size(), hoverY);
        }

        /**
         * 对照 LucidBossCompat.createButterflies：setPosition + spawnMonster。
         * 射手是 8880112（金火）；弹道是它的 type=2 ball。不要用 8880102。
         */
        private void queueShooter(Point perch, long startAt) {
            long delay = Math.max(0, startAt - System.currentTimeMillis());
            Point spawnAt = new Point(perch);
            spawnTasks.add(TimerManager.getInstance().schedule(() -> spawnShooter(spawnAt), delay));
        }

        private void spawnShooter(Point position) {
            if (!active) {
                return;
            }
            Monster shooter = LifeFactory.getMonster(SKILL2_ORB_MOB);
            if (shooter == null) {
                log.error("[DamienCompat] missing 8880112 shooter");
                return;
            }
            shooter.setPosition(new Point(position));
            map.spawnMonster(shooter);
            shooterOids.add(shooter.getObjectId());
        }

        @Override
        public void run() {
            if (!active) {
                return;
            }
            if (boss == null || !boss.isAlive() || boss.getMap() != map) {
                stop();
                return;
            }
            for (int oid : shooterOids) {
                Monster shooter = map.getMonsterByOid(oid);
                if (shooter == null || !shooter.isAlive()) {
                    continue;
                }
                Point from = new Point(shooter.getPosition());
                if (from.y >= hoverY) {
                    continue;
                }
                flyShift(map, shooter, new Point(from.x, Math.min(hoverY, from.y + FLY_STEP)));
            }
        }

        private void stop() {
            active = false;
            if (task != null) {
                task.cancel(false);
                task = null;
            }
            for (ScheduledFuture<?> spawn : spawnTasks) {
                spawn.cancel(false);
            }
            spawnTasks.clear();
            for (int oid : shooterOids) {
                Monster shooter = map.getMonsterByOid(oid);
                if (shooter != null) {
                    map.killMonster(shooter, null, false);
                }
            }
            shooterOids.clear();
            SKILL2_FIELDS.remove(map, this);
        }
    }

    /** 二阶段：2 个 8880112 巡逻、8880113 暗影球、8880114 横向 8 字/椭圆飞。 */
    private static final class PhaseTwoField implements Runnable {
        private final MapleMap map;
        private final List<Integer> shooterOids = new ArrayList<>();
        private final List<Integer> patrolOids = new ArrayList<>();
        private final List<Integer> swordOids = new ArrayList<>();
        private final ConcurrentMap<Integer, Integer> dirs = new ConcurrentHashMap<>();
        private final ConcurrentMap<Integer, Integer> swordPattern = new ConcurrentHashMap<>();
        private final ConcurrentMap<Integer, Double> swordPhase = new ConcurrentHashMap<>();
        private Monster boss;
        private ScheduledFuture<?> task;
        private volatile boolean active = true;
        private volatile boolean booted = false;
        private int hoverY;
        private int groundY;

        private PhaseTwoField(MapleMap map) {
            this.map = map;
        }

        private void boot(Monster monster) {
            this.boss = monster;
            if (booted) {
                return;
            }
            booted = true;
            Point origin = new Point(monster.getPosition());
            groundY = origin.y;
            hoverY = origin.y - HOVER_OFFSET_Y;
            spawnTracked(SHADOW_ORB_MOB, new Point(origin.x, hoverY), patrolOids, 1);
            int left = patrolLeft();
            int right = patrolRight();
            int span = Math.max(1, right - left);
            for (int index = 0; index < PHASE2_ORB_COUNT; index++) {
                int x = left + (span * index) / Math.max(1, PHASE2_ORB_COUNT - 1);
                int dir = index % 2 == 0 ? 1 : -1;
                spawnTracked(SKILL2_ORB_MOB, new Point(x, groundY), shooterOids, dir);
            }
            if (SPAWN_FLYING_SWORDS) {
                for (int index = 0; index < SWORD_COUNT; index++) {
                    int x = index == 0 ? origin.x - 200 : origin.x + 200;
                    spawnTracked(FLYING_SWORD_MOB, new Point(x, hoverY), swordOids, 1);
                    int oid = swordOids.get(swordOids.size() - 1);
                    swordPattern.put(oid, index == 0 ? 0 : 2);
                    swordPhase.put(oid, index * 0.6);
                }
            }
            if (task == null || task.isCancelled()) {
                task = TimerManager.getInstance().register(this, TICK_MS, TICK_MS);
            }
            log.info("[DamienCompat] phase2 field map={} orbs=8880112 vortex=8880113 swords={} groundY={} hoverY={}",
                    map.getId(), SPAWN_FLYING_SWORDS ? SWORD_COUNT : 0, groundY, hoverY);
        }

        private void castAttack3(Monster monster) {
            this.boss = monster;
            // 二阶段金球只保留 startPhase 的 2 个，attack3 不再加刷。
        }

        private void spawnTracked(int mobId, Point position, List<Integer> bucket, int dir) {
            Monster summoned = LifeFactory.getMonster(mobId);
            if (summoned == null) {
                log.error("[DamienCompat] missing field mob {}", mobId);
                return;
            }
            summoned.setPosition(new Point(position));
            map.spawnMonster(summoned);
            bucket.add(summoned.getObjectId());
            dirs.put(summoned.getObjectId(), dir);
        }

        private int patrolLeft() {
            FootholdTree tree = map.getFootholds();
            int min = tree.getMinDropX();
            int max = tree.getMaxDropX();
            if (max - min < 400) {
                return boss.getPosition().x - 720;
            }
            return min + 40;
        }

        private int patrolRight() {
            FootholdTree tree = map.getFootholds();
            int min = tree.getMinDropX();
            int max = tree.getMaxDropX();
            if (max - min < 400) {
                return boss.getPosition().x + 720;
            }
            return max - 40;
        }

        @Override
        public void run() {
            if (!active) {
                return;
            }
            if (boss == null || !boss.isAlive() || boss.getMap() != map) {
                stop();
                return;
            }
            int left = patrolLeft();
            int right = patrolRight();
            for (int oid : shooterOids) {
                patrolX(oid, left, right, FLY_STEP, groundY);
            }
            for (int oid : patrolOids) {
                patrolX(oid, left, right, FLY_STEP, hoverY);
            }
            chaseSwords();
        }

        private void chaseSwords() {
            if (!SPAWN_FLYING_SWORDS || swordOids.isEmpty()) {
                return;
            }
            Point center = new Point(boss.getPosition().x, hoverY);
            int ampX = Math.max(SWORD_AMP_X_MIN, (patrolRight() - patrolLeft()) * 2 / 5);
            for (int oid : swordOids) {
                Monster sword = map.getMonsterByOid(oid);
                if (sword == null || !sword.isAlive()) {
                    continue;
                }
                double t = swordPhase.merge(oid, SWORD_PATH_STEP, Double::sum);
                int pattern = swordPattern.getOrDefault(oid, 0);
                Point next = swordPathPoint(pattern, t, center, ampX, SWORD_AMP_Y);
                Point ahead = swordPathPoint(pattern, t + SWORD_PATH_STEP, center, ampX, SWORD_AMP_Y);
                flyShift(map, sword, next, ahead.x - next.x, ahead.y - next.y, true);
            }
        }

        private void patrolX(int oid, int left, int right, int step, int perchY) {
            Monster mob = map.getMonsterByOid(oid);
            if (mob == null || !mob.isAlive()) {
                return;
            }
            Point from = new Point(mob.getPosition());
            int y = from.y < perchY ? Math.min(perchY, from.y + step) : perchY;
            int dir = dirs.getOrDefault(oid, 1);
            int nextX = from.x + dir * step;
            if (nextX <= left || nextX >= right) {
                dir = -dir;
                dirs.put(oid, dir);
                nextX = from.x + dir * step;
            }
            flyShift(map, mob, new Point(nextX, y));
        }

        private void stop() {
            active = false;
            if (task != null) {
                task.cancel(false);
                task = null;
            }
            killAll(shooterOids);
            killAll(patrolOids);
            killAll(swordOids);
            dirs.clear();
            swordPattern.clear();
            swordPhase.clear();
            PHASE2_FIELDS.remove(map, this);
        }

        private void killAll(List<Integer> oids) {
            for (int oid : oids) {
                Monster mob = map.getMonsterByOid(oid);
                if (mob != null) {
                    map.killMonster(mob, null, false);
                }
            }
            oids.clear();
        }
    }
}
