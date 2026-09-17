package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.awt.Rectangle;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import java.util.concurrent.ConcurrentHashMap;
import org.gms.client.Character;
import org.gms.constants.game.CharacterStance;
import org.gms.server.maps.Foothold;
import org.gms.server.maps.FootholdTree;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Rope;
import soloMapling.ArtificialPlayer.GCMoveSystem.BotNavigationGraph;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine.class */
final class BotPhysicsEngine {
    private static final double CLIENT_GROUND_STEP_MS = 8.0d;
    private static final double CLIENT_GROUND_STEP_S = 0.008d;
    private static final int POST_LANDING_BRAKE_TICK_CAP = 240;
    private static final int REGION_STITCH_GAP_PX = 2;
    private static final int SYNTHETIC_MAP_BOUND_SIZE = 262144;
    static final int WALK_GAP_PX = 12;
    private static final int FALL_SIM_TICK_CAP = 2000;
    static final int TOP_EXIT_UP_TOL = 24;
    static final int TOP_EXIT_DOWN_TOL = 20;
    static final int TOP_EXIT_X_TOL = 8;
    private static final int GROUND_BUCKET_SHIFT = 6;
    static Config cfg = new Config();
    private static final ThreadLocal<WalkRegionLookup> ACTIVE_BUILD_WALK_REGION_LOOKUP = new ThreadLocal<>();
    private static final Map<Integer, Map<Integer, Foothold>> FOOTHOLDS_BY_ID_BY_MAP_ID = new ConcurrentHashMap();
    private static final Foothold[] NO_FOOTHOLDS = new Foothold[0];
    private static final Map<FootholdTree, FootholdCollisionIndex> COLLISION_INDEX = Collections.synchronizedMap(new WeakHashMap());
    private static final FootholdCollisionIndex UNINDEXABLE = new FootholdCollisionIndex(List.of(), List.of(), 0, new Foothold[0][]);

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$AirCollisionType.class */
    private enum AirCollisionType {
        NONE,
        WALL,
        CEILING,
        LAND
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$AirborneStepResult.class */
    enum AirborneStepResult {
        WALL,
        CEILING,
        LANDED,
        CONTINUE
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$Config.class */
    static class Config {
        public int TICK_MS = 50;
        public int WALK_VEL = 125;
        public float GRAVITY_PXS2 = 2000.0f;
        public float JUMP_SPEED_PXS = 555.0f;
        public float JUMP_DOWN_PXS = 196.0f;
        public float JUMP_ROPE_PXS = 375.0f;
        public float FLASH_JUMP_H_PXS = 550.0f;
        public float FLASH_JUMP_V_PXS = -350.0f;
        public float MAX_FALL_PXS = 670.0f;
        public double HFORCE_PXS = 16.667d;
        public double GROUNDSLIP = 3.0d;
        public double FRICTION = 0.3d;
        public double SLOPEFACTOR = 0.1d;
        public double SLIP_WALK_ACCEL_PXSS = 1400.0d;
        public double SLIP_GLIDE_DECEL_PXSS = 400.0d;
        public double AIR_CONTROL_ACCEL_PXSS = 200.0d;
        public double AIR_INPUT_BAND_DIVISOR = 14.0d;
        public double AIR_DRAG_PXSS = 1.0d;
        public double AIR_DRAG_TERMINAL_PXSS = 100.0d;
        public float CLIMB_SPEED_PXS = 100.0f;
        public int ROPE_GRAB_X = BotPhysicsEngine.TOP_EXIT_X_TOL;
        public int MAX_SNAP_DROP = 16;
        public int MAX_SLOPE_UP = 26;
        public int DOWN_JUMP_GRACE_MS = 350;
        public float SWIM_VEL_PXS = 140.0f;
        public float SWIM_GRAVITY_PXS2 = 590.0f;
        public float SWIM_FRICTION_HZ = 4.21f;
        public float SWIM_ACCEL_PXS2 = 600.0f;
        public float SWIM_MAX_SPEED_PXS = 800.0f;
        public int SWIM_ARRIVAL_RADIUS_PX = BotPhysicsEngine.TOP_EXIT_X_TOL;
        public float SWIM_JUMP_BURST_PXS = 1000.0f;
        public float SWIM_UP_THRUST_PXS2 = 412.0f;
        public float SWIM_DOWN_THRUST_PXS2 = 295.0f;
        public float SWIM_FREE_MAX_SINK_PXS = 140.0f;
        public float SWIM_DOWN_MAX_SPEED_PXS = 210.0f;
        public float SWIM_UP_MAX_SINK_PXS = 42.0f;
        public int SWIM_JUMP_COOLDOWN_MS = 500;
        public int SWIM_LEVEL_BAND_PX = 30;
        public int SWIM_DOWN_BAND_PX = 120;
        public int SWIM_JUMP_TRIGGER_DY_PX = 100;

        Config() {
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$GroundMotion.class */
    static final class GroundMotion {
        private final int stepX;
        private final boolean lostGround;

        GroundMotion(int stepX, boolean lostGround) {
            this.stepX = stepX;
            this.lostGround = lostGround;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public int stepX() {
            return this.stepX;
        }

        public boolean lostGround() {
            return this.lostGround;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$GroundTravelState.class */
    static final class GroundTravelState {
        private final double physX;
        private final double hspeed;
        private final double carryMs;

        GroundTravelState(double physX, double hspeed, double carryMs) {
            this.physX = physX;
            this.hspeed = hspeed;
            this.carryMs = carryMs;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public double physX() {
            return this.physX;
        }

        public double hspeed() {
            return this.hspeed;
        }

        public double carryMs() {
            return this.carryMs;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$GroundStepResult.class */
    static final class GroundStepResult {
        private final Point point;
        private final Foothold foothold;
        private final GroundTravelState state;
        private final int stepX;
        private final int velocityX;
        private final boolean lostGround;

        GroundStepResult(Point point, Foothold foothold, GroundTravelState state, int stepX, int velocityX, boolean lostGround) {
            this.point = point;
            this.foothold = foothold;
            this.state = state;
            this.stepX = stepX;
            this.velocityX = velocityX;
            this.lostGround = lostGround;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public Point point() {
            return this.point;
        }

        public Foothold foothold() {
            return this.foothold;
        }

        public GroundTravelState state() {
            return this.state;
        }

        public int stepX() {
            return this.stepX;
        }

        public int velocityX() {
            return this.velocityX;
        }

        public boolean lostGround() {
            return this.lostGround;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$GroundRegionSample.class */
    private static final class GroundRegionSample {
        private final Point point;
        private final Foothold foothold;

        private GroundRegionSample(Point point, Foothold foothold) {
            this.point = point;
            this.foothold = foothold;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public Point point() {
            return this.point;
        }

        public Foothold foothold() {
            return this.foothold;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$GroundStepPreview.class */
    private static final class GroundStepPreview {
        private final int baseY;
        private final Point point;
        private final Foothold foothold;
        private final boolean lostGround;
        private final boolean blocked;

        private GroundStepPreview(int baseY, Point point, Foothold foothold, boolean lostGround, boolean blocked) {
            this.baseY = baseY;
            this.point = point;
            this.foothold = foothold;
            this.lostGround = lostGround;
            this.blocked = blocked;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public int baseY() {
            return this.baseY;
        }

        public Point point() {
            return this.point;
        }

        public Foothold foothold() {
            return this.foothold;
        }

        public boolean lostGround() {
            return this.lostGround;
        }

        public boolean blocked() {
            return this.blocked;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$WalkRegionLookup.class */
    private static final class WalkRegionLookup {
        private final int mapId;
        private final Map<Integer, BotNavigationGraph.Region> regionsById;
        private final Map<Integer, Integer> regionIdByFootholdId;
        private final Map<Integer, Foothold> footholdsById;

        private WalkRegionLookup(int mapId, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, Foothold> footholdsById) {
            this.mapId = mapId;
            this.regionsById = regionsById;
            this.regionIdByFootholdId = regionIdByFootholdId;
            this.footholdsById = footholdsById;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public int mapId() {
            return this.mapId;
        }

        public Map<Integer, BotNavigationGraph.Region> regionsById() {
            return this.regionsById;
        }

        public Map<Integer, Integer> regionIdByFootholdId() {
            return this.regionIdByFootholdId;
        }

        public Map<Integer, Foothold> footholdsById() {
            return this.footholdsById;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$MovementSnapshot.class */
    static final class MovementSnapshot {
        private final int velX;
        private final int velY;
        private final int stance;

        MovementSnapshot(int velX, int velY, int stance) {
            this.velX = velX;
            this.velY = velY;
            this.stance = stance;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public int velX() {
            return this.velX;
        }

        public int velY() {
            return this.velY;
        }

        public int stance() {
            return this.stance;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$JumpLanding.class */
    static final class JumpLanding {
        private final Point point;
        private final Foothold foothold;
        private final double incomingDeltaX;
        private final double incomingDeltaY;
        private final int ticks;

        JumpLanding(Point point, Foothold foothold) {
            this(point, foothold, 0.0d, 0.0d, 0);
        }

        JumpLanding(Point point, Foothold foothold, double incomingDeltaX, double incomingDeltaY) {
            this(point, foothold, incomingDeltaX, incomingDeltaY, 0);
        }

        JumpLanding(Point point, Foothold foothold, double incomingDeltaX, double incomingDeltaY, int ticks) {
            this.point = point;
            this.foothold = foothold;
            this.incomingDeltaX = incomingDeltaX;
            this.incomingDeltaY = incomingDeltaY;
            this.ticks = ticks;
        }

        Point point() {
            return this.point;
        }

        Foothold foothold() {
            return this.foothold;
        }

        double incomingDeltaX() {
            return this.incomingDeltaX;
        }

        double incomingDeltaY() {
            return this.incomingDeltaY;
        }

        int timeMs() {
            return this.ticks * BotPhysicsEngine.cfg.TICK_MS;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$PostLandingJump.class */
    static final class PostLandingJump {
        private final JumpLanding landing;
        private final Point finalPoint;
        private final Foothold finalFoothold;
        private final boolean lostGround;

        PostLandingJump(JumpLanding landing, Point finalPoint, Foothold finalFoothold, boolean lostGround) {
            this.landing = landing;
            this.finalPoint = finalPoint;
            this.finalFoothold = finalFoothold;
            this.lostGround = lostGround;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public JumpLanding landing() {
            return this.landing;
        }

        public Point finalPoint() {
            return this.finalPoint;
        }

        public Foothold finalFoothold() {
            return this.finalFoothold;
        }

        public boolean lostGround() {
            return this.lostGround;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$WalkOffLanding.class */
    static final class WalkOffLanding {
        private final Point launchPoint;
        private final int launchStepX;
        private final JumpLanding landing;
        private final int travelTimeMs;

        WalkOffLanding(Point launchPoint, int launchStepX, JumpLanding landing, int travelTimeMs) {
            this.launchPoint = launchPoint;
            this.launchStepX = launchStepX;
            this.landing = landing;
            this.travelTimeMs = travelTimeMs;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public Point launchPoint() {
            return this.launchPoint;
        }

        public int launchStepX() {
            return this.launchStepX;
        }

        public JumpLanding landing() {
            return this.landing;
        }

        public int travelTimeMs() {
            return this.travelTimeMs;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$AirCollision.class */
    private static final class AirCollision {
        private final AirCollisionType type;
        private final Point point;
        private final Foothold foothold;
        private final double progress;

        private AirCollision(AirCollisionType type, Point point, Foothold foothold, double progress) {
            this.type = type;
            this.point = point;
            this.foothold = foothold;
            this.progress = progress;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public AirCollisionType type() {
            return this.type;
        }

        public Point point() {
            return this.point;
        }

        public Foothold foothold() {
            return this.foothold;
        }

        public double progress() {
            return this.progress;
        }

        static AirCollision none() {
            return new AirCollision(AirCollisionType.NONE, null, null, Double.POSITIVE_INFINITY);
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$RopeGrabResult.class */
    private static final class RopeGrabResult {
        private final Point point;
        private final int ticks;

        private RopeGrabResult(Point point, int ticks) {
            this.point = point;
            this.ticks = ticks;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public Point point() {
            return this.point;
        }

        public int ticks() {
            return this.ticks;
        }
    }

    private BotPhysicsEngine() {
    }

    private static BotMovementProfile profileOrBase(BotMovementProfile profile) {
        return profile != null ? profile : BotMovementProfile.base();
    }

    static float tickS() {
        return cfg.TICK_MS / 1000.0f;
    }

    static float maxFallPerTick() {
        return cfg.MAX_FALL_PXS * tickS();
    }

    private static int mapFloorY(MapleMap map) {
        Rectangle area = map == null ? null : map.getMapArea();
        if (area == null || area.height <= 0) {
            return Integer.MAX_VALUE;
        }
        return area.y + area.height + 600;
    }

    static float jumpForcePerTick() {
        return cfg.JUMP_SPEED_PXS * tickS();
    }

    static float jumpForcePerTick(BotMovementProfile profile) {
        return profileOrBase(profile).jumpSpeedPxs() * tickS();
    }

    static float downJumpForcePerTick() {
        return cfg.JUMP_DOWN_PXS * tickS();
    }

    static float ropeJumpForcePerTick() {
        return cfg.JUMP_ROPE_PXS * tickS();
    }

    static float ropeJumpForcePerTick(BotMovementProfile profile) {
        return profileOrBase(profile).ropeJumpSpeedPxs() * tickS();
    }

    static float flashJumpHPerTick() {
        return cfg.FLASH_JUMP_H_PXS * tickS();
    }

    static float flashJumpVPerTick() {
        return cfg.FLASH_JUMP_V_PXS * tickS();
    }

    static float flashJumpTriggerVelY(BotMovementState entry) {
        return (-(1.0f - entry.flashJumpScale)) * jumpForcePerTick(entry.movementProfile);
    }

    static int climbStepPerTick() {
        return Math.max(1, Math.round(cfg.CLIMB_SPEED_PXS * tickS()));
    }

    static float gravityPerTick() {
        float t = tickS();
        return cfg.GRAVITY_PXS2 * t * t;
    }

    static int walkStep(MapleMap map) {
        return walkStep(map, BotMovementProfile.base());
    }

    static int walkStep(MapleMap map, BotMovementProfile profile) {
        double step = (maxHSpeedPerClientStep(profile) * cfg.TICK_MS) / CLIENT_GROUND_STEP_MS;
        return Math.max(1, (int) Math.round(step));
    }

    static int launchRunwayPx(MapleMap map, BotMovementProfile profile) {
        int step = walkStep(map, profile);
        double fs = mapGroundSlipScale(map, profile);
        if (fs >= 1.0d) {
            return Math.max(40, step * GROUND_BUCKET_SHIFT);
        }
        double vmaxPxs = maxHSpeedPerClientStep(profile) / CLIENT_GROUND_STEP_S;
        double accelDistPx = (vmaxPxs * vmaxPxs) / ((2.0d * cfg.SLIP_WALK_ACCEL_PXSS) * fs);
        return (int) Math.max(40L, Math.round((step * GROUND_BUCKET_SHIFT) + accelDistPx));
    }

    static int velocityFromDeltaX(double deltaX) {
        return (int) Math.round(deltaX * (1000.0d / cfg.TICK_MS));
    }

    static void syncGroundPosition(BotMovementState entry, int x) {
        if (entry.hspeed == 0.0d && ((int) Math.round(entry.physX)) != x) {
            entry.physX = x;
        }
    }

    static Foothold syncAndDetectGround(BotMovementState entry, Character bot) {
        syncGroundPosition(entry, bot.getPosition().x);
        Foothold fh = findGroundFoothold(bot.getMap(), bot.getPosition());
        if (fh == null) {
            beginFall(entry, bot, 0);
        }
        return fh;
    }

    static Foothold findGroundFoothold(MapleMap map, Point position) {
        if (map == null || map.getFootholds() == null || position == null) {
            return null;
        }
        Foothold exact = findBelowIndexed(map, position);
        Foothold offset = findBelowIndexed(map, new Point(position.x, position.y - cfg.MAX_SLOPE_UP));
        if (exact == null) {
            return offset;
        }
        if (offset == null) {
            return exact;
        }
        Point exactGround = pointBelowIndexed(map, position);
        Point offsetGround = pointBelowIndexed(map, new Point(position.x, position.y - cfg.MAX_SLOPE_UP));
        if (exactGround == null) {
            return offset;
        }
        if (offsetGround != null && Math.abs(offsetGround.y - position.y) < Math.abs(exactGround.y - position.y)) {
            return offset;
        }
        return exact;
    }

    static Point findGroundPoint(MapleMap map, Point position) {
        if (map == null || position == null) {
            return null;
        }
        Point exactGround = pointBelowIndexed(map, position);
        Point offsetGround = pointBelowIndexed(map, new Point(position.x, position.y - cfg.MAX_SLOPE_UP));
        if (exactGround == null) {
            return offsetGround;
        }
        if (offsetGround == null) {
            return exactGround;
        }
        int exactDistance = Math.abs(exactGround.y - position.y);
        int offsetDistance = Math.abs(offsetGround.y - position.y);
        return offsetDistance < exactDistance ? offsetGround : exactGround;
    }

    static boolean canWalkAcrossFootholds(Foothold first, Foothold second) {
        if (first == null || second == null || first.isWall() || second.isWall()) {
            return false;
        }
        EndpointConnection connection = sharedEndpointConnection(first, second);
        if (connection == null) {
            connection = closestEndpointConnection(first, second);
            if (connection == null || Math.abs(connection.to().x - connection.from().x) + Math.abs(connection.to().y - connection.from().y) > REGION_STITCH_GAP_PX) {
                return false;
            }
        }
        int dx = Math.abs(connection.to().x - connection.from().x);
        int dy = connection.to().y - connection.from().y;
        if (!isWalkableEndpointStep(dx, dy)) {
            return false;
        }
        return true;
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$EndpointConnection.class */
    private static final class EndpointConnection {
        private final Point from;
        private final Point to;

        private EndpointConnection(Point from, Point to) {
            this.from = from;
            this.to = to;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public Point from() {
            return this.from;
        }

        public Point to() {
            return this.to;
        }
    }

    private static Point[] endpoints(Foothold fh) {
        return new Point[]{new Point(fh.getX1(), fh.getY1()), new Point(fh.getX2(), fh.getY2())};
    }

    private static EndpointConnection closestEndpointConnection(Foothold first, Foothold second) {
        EndpointConnection best = null;
        int bestDistance = Integer.MAX_VALUE;
        for (Point from : endpoints(first)) {
            for (Point to : endpoints(second)) {
                int distance = Math.abs(to.x - from.x) + Math.abs(to.y - from.y);
                if (distance < bestDistance) {
                    best = new EndpointConnection(from, to);
                    bestDistance = distance;
                }
            }
        }
        return best;
    }

    private static EndpointConnection sharedEndpointConnection(Foothold first, Foothold second) {
        for (Point from : endpoints(first)) {
            for (Point to : endpoints(second)) {
                if (from.equals(to)) {
                    return new EndpointConnection(from, to);
                }
            }
        }
        return null;
    }

    static Point findWalkRegionGroundPoint(MapleMap map, Foothold foothold, int x, int referenceY) {
        GroundRegionSample sample = findWalkRegionGroundSample(map, foothold, x, referenceY);
        if (sample == null) {
            return null;
        }
        return sample.point();
    }

    static boolean canWalkGroundStep(MapleMap map, Point currentPos, int stepX) {
        if (map == null || currentPos == null) {
            return false;
        }
        Foothold foothold = findGroundFoothold(map, currentPos);
        GroundStepPreview preview = previewGroundStep(map, currentPos, foothold, currentPos.x + stepX);
        return (preview == null || preview.lostGround() || preview.blocked()) ? false : true;
    }

    static boolean isGroundStepBlockedByWall(MapleMap map, Point currentPos, int stepX) {
        if (map == null || currentPos == null || stepX == 0) {
            return false;
        }
        Foothold foothold = findGroundFoothold(map, currentPos);
        GroundStepPreview preview = previewGroundStep(map, currentPos, foothold, currentPos.x + stepX);
        return preview != null && preview.blocked();
    }

    static boolean isGroundRunwayBlockedByWall(MapleMap map, Point from, Point to) {
        return findGroundWallCollision(map, from, to).type() == AirCollisionType.WALL;
    }

    static boolean isGroundFarBelow(MapleMap map, Point position) {
        Point ground;
        return map == null || position == null || (ground = findGroundPoint(map, position)) == null || ground.y > position.y + cfg.MAX_SNAP_DROP;
    }

    private static boolean hasWalkRegion(MapleMap map, Foothold foothold) {
        WalkRegionLookup lookup;
        return (map == null || foothold == null || (lookup = resolveWalkRegionLookup(map)) == null || lookup.regionIdByFootholdId().getOrDefault(Integer.valueOf(foothold.getId()), -1).intValue() < 0) ? false : true;
    }

    private static GroundRegionSample findWalkRegionGroundSample(MapleMap map, Foothold foothold, int x, int referenceY) {
        WalkRegionLookup lookup;
        Foothold bestFoothold;
        if (map == null || foothold == null || (lookup = resolveWalkRegionLookup(map)) == null) {
            return null;
        }
        int regionId = lookup.regionIdByFootholdId().getOrDefault(Integer.valueOf(foothold.getId()), -1).intValue();
        BotNavigationGraph.Region region = lookup.regionsById().get(Integer.valueOf(regionId));
        if (region == null || region.isRopeRegion) {
            return null;
        }
        BotNavigationGraph.Segment bestSegment = null;
        Point bestPoint = null;
        int bestScore = Integer.MAX_VALUE;
        boolean foundContainingSegment = false;
        Iterator<BotNavigationGraph.Segment> it = region.segments.iterator();
        while (true) {
            if (!it.hasNext()) {
                break;
            }
            if (it.next().containsX(x)) {
                foundContainingSegment = true;
                break;
            }
        }
        for (BotNavigationGraph.Segment segment : region.segments) {
            int dx = distanceToSegmentX(segment, x);
            boolean containsX = segment.containsX(x);
            if (containsX || (!foundContainingSegment && dx <= REGION_STITCH_GAP_PX)) {
                Point candidate = segment.pointAt(x);
                int dy = candidate.y - referenceY;
                if (dy <= cfg.MAX_SNAP_DROP && dy >= (-cfg.MAX_SLOPE_UP)) {
                    int score = (dx * 1000) + Math.abs(dy);
                    if (bestPoint == null || score < bestScore || (score == bestScore && candidate.y > bestPoint.y)) {
                        bestSegment = segment;
                        bestPoint = candidate;
                        bestScore = score;
                    }
                }
            }
        }
        if (bestSegment == null || (bestFoothold = lookup.footholdsById().get(Integer.valueOf(bestSegment.footholdId))) == null) {
            return null;
        }
        return new GroundRegionSample(bestPoint, bestFoothold);
    }

    static void setBuildWalkRegionLookup(MapleMap map, Map<Integer, BotNavigationGraph.Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, Foothold> footholdsById) {
        if (map == null || regionsById == null || regionIdByFootholdId == null || footholdsById == null) {
            ACTIVE_BUILD_WALK_REGION_LOOKUP.remove();
        } else {
            ACTIVE_BUILD_WALK_REGION_LOOKUP.set(new WalkRegionLookup(map.getId(), regionsById, regionIdByFootholdId, footholdsById));
        }
    }

    static void clearBuildWalkRegionLookup() {
        ACTIVE_BUILD_WALK_REGION_LOOKUP.remove();
    }

    private static WalkRegionLookup resolveWalkRegionLookup(MapleMap map) {
        if (map == null) {
            return null;
        }
        WalkRegionLookup activeLookup = ACTIVE_BUILD_WALK_REGION_LOOKUP.get();
        if (activeLookup != null && activeLookup.mapId() == map.getId()) {
            return activeLookup;
        }
        BotNavigationGraph graph = BotNavigationGraphProvider.peekGraph(map);
        if (graph == null) {
            return null;
        }
        return new WalkRegionLookup(map.getId(), graph.regionsById, graph.regionIdByFootholdId, footholdsById(map));
    }

    private static Map<Integer, Foothold> footholdsById(MapleMap map) {
        if (map == null || map.getFootholds() == null) {
            return Map.of();
        }
        return FOOTHOLDS_BY_ID_BY_MAP_ID.computeIfAbsent(Integer.valueOf(map.getId()), ignored -> {
            Map<Integer, Foothold> footholdsById = new HashMap<>();
            for (Foothold foothold : map.getFootholds().getAllFootholds()) {
                footholdsById.put(Integer.valueOf(foothold.getId()), foothold);
            }
            return footholdsById;
        });
    }

    private static GroundStepPreview previewGroundStep(MapleMap map, Point currentPos, Foothold foothold, int nextX) {
        Point pointFindWalkRegionGroundPoint;
        int i;
        Point snappedPoint;
        boolean lostGround;
        Foothold footholdFindBelowIndexed;
        Foothold snappedFoothold;
        if (map == null || currentPos == null) {
            return null;
        }
        boolean constrainToWalkRegion = hasWalkRegion(map, foothold);
        if (constrainToWalkRegion) {
            pointFindWalkRegionGroundPoint = findWalkRegionGroundPoint(map, foothold, currentPos.x, currentPos.y);
        } else {
            pointFindWalkRegionGroundPoint = null;
        }
        Point standingPoint = pointFindWalkRegionGroundPoint;
        if (standingPoint == null) {
            standingPoint = findGroundPoint(map, currentPos);
        }
        if (standingPoint != null && Math.abs(standingPoint.y - currentPos.y) <= cfg.MAX_SLOPE_UP) {
            i = standingPoint.y;
        } else {
            i = currentPos.y;
        }
        int baseY = i;
        AirCollision wall = findGroundWallCollision(map, currentPos, new Point(nextX, baseY));
        if (wall.type() == AirCollisionType.WALL) {
            return new GroundStepPreview(baseY, currentPos, foothold, false, true);
        }
        if (constrainToWalkRegion) {
            GroundRegionSample snappedSample = findWalkRegionGroundSample(map, foothold, nextX, baseY);
            snappedPoint = snappedSample == null ? null : snappedSample.point();
            snappedFoothold = snappedSample == null ? null : snappedSample.foothold();
            lostGround = snappedPoint == null || snappedPoint.y > baseY + cfg.MAX_SNAP_DROP;
        } else {
            int probeY = Math.max(currentPos.y, baseY + 1);
            snappedPoint = findGroundPoint(map, new Point(nextX, probeY));
            lostGround = snappedPoint == null || snappedPoint.y > baseY + cfg.MAX_SNAP_DROP;
            if (snappedPoint == null || map.getFootholds() == null) {
                footholdFindBelowIndexed = null;
            } else {
                footholdFindBelowIndexed = findBelowIndexed(map, new Point(nextX, snappedPoint.y + 1));
            }
            snappedFoothold = footholdFindBelowIndexed;
        }
        return new GroundStepPreview(baseY, snappedPoint, snappedFoothold, lostGround, false);
    }

    private static int distanceToSegmentX(BotNavigationGraph.Segment segment, int x) {
        if (segment.containsX(x)) {
            return 0;
        }
        return x < segment.minX ? segment.minX - x : x - segment.maxX;
    }

    static void stopGroundMotion(BotMovementState entry) {
        entry.hspeed = 0.0d;
    }

    static void resetMotion(BotMovementState entry, Point position) {
        clearMovementState(entry, position);
        syncCharacterState(entry);
    }

    static void teleportTo(BotMovementState entry, Character bot, Point position) {
        bot.setPosition(position);
        clearMovementState(entry, position);
        syncCharacterState(entry);
    }

    static void beginPortalDrop(BotMovementState entry, Character bot, Point spawn) {
        bot.setPosition(spawn);
        clearMovementState(entry, spawn);
        entry.inAir = true;
        entry.velY = 0.0f;
        entry.fallPeakPhysY = spawn.y;
        syncCharacterState(entry);
    }

    static void markDead(BotMovementState entry, Character bot) {
        clearMovementState(entry, bot.getPosition());
        syncCharacterState(entry);
    }

    static void idleOnGround(BotMovementState entry, Character bot) {
        Point position = bot.getPosition();
        entry.inAir = false;
        entry.climbing = false;
        entry.climbRope = null;
        entry.crouching = false;
        entry.climbUpIntent = false;
        clearRopeEntryIntent(entry);
        entry.velY = 0.0f;
        entry.airVelX = 0;
        entry.airSteerVelX = 0.0d;
        entry.fixedAirArc = false;
        entry.moveDir = 0;
        entry.groundBrakeDir = 0;
        entry.physX = position.x;
        entry.physY = position.y;
        stopGroundMotion(entry);
        setMovementVelocity(entry, 0, 0);
        syncCharacterState(entry);
    }

    static void proneOnGround(BotMovementState entry, Character bot) {
        idleOnGround(entry, bot);
        entry.crouching = true;
        entry.downJumpPending = false;
        syncCharacterState(entry);
    }

    static void queueDownJump(BotMovementState entry, Character bot) {
        idleOnGround(entry, bot);
        entry.downJumpPending = true;
        entry.crouching = true;
        syncCharacterState(entry);
    }

    static void queueTopRopeEntry(BotMovementState entry, Character bot, Rope rope, int y) {
        idleOnGround(entry, bot);
        entry.ropeEntryPending = true;
        entry.ropeEntryRope = rope;
        entry.ropeEntryY = y;
        syncCharacterState(entry);
    }

    static void beginGroundJump(BotMovementState entry, Character bot, int airVelX) {
        entry.blockedRopeGrab = null;
        if (bot.getMap() != null && bot.getMap().isSwim()) {
            Point position = bot.getPosition();
            entry.climbing = false;
            entry.climbRope = null;
            entry.inAir = true;
            entry.swimming = true;
            entry.crouching = false;
            entry.physX = position.x;
            entry.physY = position.y;
            entry.velY = -profileOrBase(entry.movementProfile).jumpSpeedPxs();
            stopGroundMotion(entry);
            entry.climbUpIntent = false;
            entry.airVelX = 0;
            entry.airSteerVelX = 0.0d;
            entry.fixedAirArc = false;
            entry.downJumpPending = false;
            entry.swimJumpRequested = false;
            entry.swimNextJumpAtMs = System.currentTimeMillis() + cfg.SWIM_JUMP_COOLDOWN_MS;
            setMovementVelocity(entry, 0, Math.round(entry.velY));
            syncCharacterState(entry);
            return;
        }
        launchAirborne(entry, bot, bot.getPosition(), -jumpForcePerTick(entry.movementProfile), airVelX, false);
    }

    static void beginClimbUpJump(BotMovementState entry, Character bot, int airVelX) {
        entry.blockedRopeGrab = null;
        launchAirborne(entry, bot, bot.getPosition(), -jumpForcePerTick(entry.movementProfile), airVelX, true);
    }

    static void beginJumpOffRope(BotMovementState entry, Character bot, int airVelX) {
        entry.blockedRopeGrab = null;
        launchAirborne(entry, bot, bot.getPosition(), -ropeJumpForcePerTick(entry.movementProfile), airVelX, false);
    }

    static void beginRopeTransferJump(BotMovementState entry, Character bot, Rope sourceRope, int airVelX) {
        entry.blockedRopeGrab = sourceRope;
        launchAirborne(entry, bot, bot.getPosition(), -ropeJumpForcePerTick(entry.movementProfile), airVelX, true);
    }

    static void beginDownJump(BotMovementState entry, Character bot) {
        if (!canStartDownJump(bot.getMap(), bot.getPosition())) {
            entry.downJumpPending = false;
            entry.downJumpGracePeriodMS = 0L;
            entry.crouching = false;
            syncCharacterState(entry);
            return;
        }
        entry.blockedRopeGrab = null;
        launchAirborne(entry, bot, bot.getPosition(), -downJumpForcePerTick(), 0, false);
        entry.downJumpGracePeriodMS = cfg.DOWN_JUMP_GRACE_MS;
    }

    static void beginTopRopeEntry(BotMovementState entry, Character bot) {
        Rope rope = entry.ropeEntryRope;
        int ropeY = entry.ropeEntryY;
        clearRopeEntryIntent(entry);
        if (rope == null || bot == null) {
            syncCharacterState(entry);
            return;
        }
        Point position = bot.getPosition();
        if (position == null || Math.abs(position.x - rope.x()) > cfg.ROPE_GRAB_X) {
            syncCharacterState(entry);
        } else {
            attachToRope(entry, bot, rope, ropeY);
        }
    }

    static void executeDrop(BotMovementState entry, Character bot, int airVelX) {
        beginFall(entry, bot, airVelX);
    }

    private static void beginFall(BotMovementState entry, Character bot, int airVelX) {
        beginFall(entry, bot, bot.getPosition(), airVelX);
    }

    private static void beginFall(BotMovementState entry, Character bot, Point position, int airVelX) {
        entry.blockedRopeGrab = null;
        bot.setPosition(new Point(position));
        launchAirborne(entry, bot, position, 0.0f, airVelX, false);
    }

    static void beginKnockback(BotMovementState entry, Character bot, Point position, float initialVelY, int airVelX) {
        int preservedFacingDir = entry.facingDir;
        bot.setPosition(position);
        entry.blockedRopeGrab = null;
        launchAirborne(entry, bot, position, initialVelY, airVelX, true);
        entry.facingDir = preservedFacingDir;
        syncCharacterState(entry);
    }

    static void applyAirKnockback(BotMovementState entry, Character bot, int airVelX) {
        int preservedFacingDir = entry.facingDir;
        Point position = bot.getPosition();
        entry.inAir = true;
        entry.climbing = false;
        entry.climbRope = null;
        entry.crouching = false;
        entry.physX = position.x;
        entry.physY = position.y;
        stopGroundMotion(entry);
        entry.climbUpIntent = true;
        entry.airVelX = airVelX;
        entry.airSteerVelX = 0.0d;
        entry.fixedAirArc = false;
        entry.downJumpPending = false;
        entry.blockedRopeGrab = null;
        setMovementVelocity(entry, velocityFromDeltaX(airVelX), velocityFromAirStep(entry.velY));
        entry.facingDir = preservedFacingDir;
        syncCharacterState(entry);
    }

    private static void landOnGround(BotMovementState entry, Character bot, Point position) {
        landOnGround(entry, bot, position, null, 0.0d, 0.0d);
    }

    private static void landOnGround(BotMovementState entry, Character bot, Point position, Foothold foothold, double incomingDeltaX, double incomingDeltaY) {
        double dMax;
        if (Double.isFinite(entry.fallPeakPhysY)) {
            dMax = Math.max(0.0d, position.y - entry.fallPeakPhysY);
        } else {
            dMax = 0.0d;
        }
        double fallDistance = dMax;
        bot.setPosition(position);
        entry.inAir = false;
        entry.climbing = false;
        entry.climbRope = null;
        entry.crouching = false;
        entry.climbUpIntent = false;
        entry.velY = 0.0f;
        entry.airVelX = 0;
        entry.airSteerVelX = 0.0d;
        entry.fixedAirArc = false;
        entry.pendingFlashJump = false;
        entry.flashJumpFired = false;
        entry.physX = position.x;
        entry.physY = position.y;
        clearRopeEntryIntent(entry);
        entry.downJumpPending = false;
        entry.downJumpGracePeriodMS = 0L;
        entry.groundPhysicsCarryMs = 0.0d;
        entry.blockedRopeGrab = null;
        entry.hspeed = landingGroundHSpeed(bot.getMap(), foothold, incomingDeltaX, incomingDeltaY, entry.movementProfile);
        entry.groundBrakeDir = 0;
        setMovementVelocity(entry, velocityFromDeltaX(tickDeltaFromGroundHSpeed(bot.getMap(), entry.hspeed, entry.movementProfile)), 0);
        syncCharacterState(entry);
        BotContactDamage.applyFallDamage(entry, bot, (float) fallDistance);
        entry.fallPeakPhysY = Double.POSITIVE_INFINITY;
    }

    static void attachToRope(BotMovementState entry, Character bot, Rope rope, int y) {
        int ropeY = Math.clamp(y, firstClimbableY(rope), rope.bottomY());
        entry.climbVerticalDir = 0;
        setClimbPosition(entry, bot, rope, ropeY);
    }

    static void advanceClimb(BotMovementState entry, Character bot) {
        Rope rope = entry.climbRope;
        if (rope == null) {
            beginFall(entry, bot, 0);
            return;
        }
        int climbDir = Integer.compare(entry.climbVerticalDir, 0);
        if (climbDir == 0) {
            holdClimb(entry, bot);
            return;
        }
        int nextY = bot.getPosition().y + (climbDir * climbStepPerTick());
        if (resolveClimbBoundary(entry, bot, rope, nextY)) {
            return;
        }
        setClimbPosition(entry, bot, rope, nextY);
    }

    static void holdClimb(BotMovementState entry, Character bot) {
        Rope rope = entry.climbRope;
        if (rope == null) {
            beginFall(entry, bot, 0);
        } else {
            if (resolveClimbBoundary(entry, bot, rope, bot.getPosition().y)) {
                return;
            }
            setMovementVelocity(entry, 0, 0);
            syncCharacterState(entry);
        }
    }

    static void tickMotionTimers(BotMovementState entry) {
        if (entry.downJumpGracePeriodMS > 0) {
            entry.downJumpGracePeriodMS = Math.max(0L, entry.downJumpGracePeriodMS - cfg.TICK_MS);
        }
    }

    static boolean canLand(BotMovementState entry) {
        return entry.downJumpGracePeriodMS == 0;
    }

    static GroundMotion applyGroundMotion(BotMovementState entry, Character bot, Foothold foothold) {
        double dPhysX;
        MapleMap map = bot.getMap();
        Point currentPos = bot.getPosition();
        int desiredDir = entry.moveDir;
        if (desiredDir == 0) {
            desiredDir = slipperyStopDir(map, entry.movementProfile, currentPos, foothold, new GroundTravelState(entry.physX, entry.hspeed, entry.groundPhysicsCarryMs));
        }
        boolean braking = desiredDir != 0 && entry.hspeed * ((double) desiredDir) < 0.0d;
        GroundStepResult step = simulateGroundMotion(map, currentPos, foothold, desiredDir, new GroundTravelState(entry.physX, entry.hspeed, entry.groundPhysicsCarryMs), entry.movementProfile);
        if (step.lostGround()) {
            beginFall(entry, bot, step.point(), step.stepX());
            return new GroundMotion(step.stepX(), true);
        }
        Point position = step.point();
        bot.setPosition(position);
        entry.inAir = false;
        entry.climbing = false;
        entry.climbRope = null;
        entry.crouching = false;
        entry.climbUpIntent = false;
        entry.velY = 0.0f;
        entry.airVelX = 0;
        entry.airSteerVelX = 0.0d;
        entry.fixedAirArc = false;
        if (mapGroundSlipScale(map, entry.movementProfile) < 1.0d) {
            dPhysX = step.state().physX();
        } else {
            dPhysX = position.x;
        }
        entry.physX = dPhysX;
        entry.physY = position.y;
        entry.hspeed = step.state().hspeed();
        entry.groundPhysicsCarryMs = step.state().carryMs();
        entry.downJumpPending = false;
        int preMoveFacing = entry.facingDir;
        boolean movedThisTick = position.x != currentPos.x;
        setMovementVelocity(entry, step.velocityX(), 0);
        entry.groundBrakeDir = (braking && movedThisTick) ? desiredDir : 0;
        if (movedThisTick && desiredDir != 0) {
            entry.facingDir = desiredDir;
        } else {
            entry.facingDir = preMoveFacing;
        }
        syncCharacterState(entry);
        return new GroundMotion(step.stepX(), false);
    }

    static GroundTravelState initialGroundTravelState(Point position) {
        return new GroundTravelState(position.x, 0.0d, 0.0d);
    }

    static GroundStepResult simulateGroundMotion(MapleMap map, Point currentPos, Foothold foothold, int desiredDir, GroundTravelState state, BotMovementProfile profile) {
        if (map == null || currentPos == null || foothold == null || state == null) {
            return new GroundStepResult(currentPos, foothold, state, 0, 0, true);
        }
        GroundTravelState displaced = applyGroundDisplacement(map, foothold, desiredDir, state, profile);
        int newX = (int) Math.round(displaced.physX());
        int stepX = newX - currentPos.x;
        GroundStepPreview preview = previewGroundStep(map, currentPos, foothold, newX);
        if (preview == null) {
            return new GroundStepResult(currentPos, foothold, state, 0, 0, true);
        }
        if (preview.blocked()) {
            return new GroundStepResult(currentPos, foothold, initialGroundTravelState(currentPos), 0, 0, false);
        }
        if (preview.lostGround()) {
            return new GroundStepResult(new Point(newX, preview.baseY()), foothold, displaced, stepX, velocityFromDeltaX(displaced.physX() - currentPos.x), true);
        }
        return new GroundStepResult(preview.point(), preview.foothold() != null ? preview.foothold() : foothold, displaced, stepX, velocityFromDeltaX(displaced.physX() - currentPos.x), false);
    }

    static WalkOffLanding simulateWalkOffLanding(MapleMap map, Point from, int desiredDir, BotMovementProfile profile) {
        return simulateWalkOffLanding(map, from, desiredDir, initialGroundTravelState(from), profile);
    }

    static WalkOffLanding simulateWalkOffLanding(MapleMap map, Point from, int desiredDir, GroundTravelState initialState, BotMovementProfile profile) {
        Foothold foothold;
        JumpLanding landing;
        if (map == null || from == null || desiredDir == 0 || initialState == null || (foothold = findGroundFoothold(map, from)) == null) {
            return null;
        }
        Point cursor = new Point(from);
        Foothold currentFoothold = foothold;
        GroundTravelState state = initialState;
        int elapsedMs = 0;
        for (int i = 0; i < 256; i++) {
            GroundStepResult step = simulateGroundMotion(map, cursor, currentFoothold, desiredDir, state, profile);
            if (step.lostGround()) {
                if (step.stepX() == 0 || (landing = simulateFallLanding(map, step.point(), step.stepX())) == null) {
                    return null;
                }
                return new WalkOffLanding(new Point(step.point()), step.stepX(), landing, elapsedMs + estimateFallLandingTimeMs(map, step.point(), step.stepX()));
            }
            cursor = step.point();
            currentFoothold = step.foothold();
            state = step.state();
            elapsedMs += cfg.TICK_MS;
        }
        return null;
    }

    static PostLandingJump simulatePostLandingGroundTicks(MapleMap map, JumpLanding landing, int desiredDir, BotMovementProfile profile, int ticks) {
        if (landing == null) {
            return null;
        }
        if (map == null || landing.point() == null || landing.foothold() == null || ticks <= 0) {
            return new PostLandingJump(landing, landing.point() == null ? null : new Point(landing.point()), landing.foothold(), false);
        }
        double landingHSpeed = landingGroundHSpeed(map, landing.foothold(), landing.incomingDeltaX(), landing.incomingDeltaY(), profile);
        GroundTravelState state = new GroundTravelState(landing.point().x, landingHSpeed, 0.0d);
        Point cursor = new Point(landing.point());
        Foothold currentFoothold = landing.foothold();
        if (mapGroundSlipScale(map, profile) < 1.0d) {
            for (int i = 0; i < POST_LANDING_BRAKE_TICK_CAP; i++) {
                int dir = slipperyStopDir(map, profile, cursor, currentFoothold, state);
                if (dir == 0) {
                    return new PostLandingJump(landing, cursor, currentFoothold, false);
                }
                GroundStepResult step = simulateGroundMotion(map, cursor, currentFoothold, dir, state, profile);
                if (step.lostGround()) {
                    return new PostLandingJump(landing, step.point(), step.foothold(), true);
                }
                cursor = step.point();
                currentFoothold = step.foothold();
                state = step.state();
            }
            return new PostLandingJump(landing, cursor, currentFoothold, true);
        }
        for (int i2 = 0; i2 < ticks; i2++) {
            GroundStepResult step2 = simulateGroundMotion(map, cursor, currentFoothold, desiredDir, state, profile);
            if (step2.lostGround()) {
                return new PostLandingJump(landing, step2.point(), step2.foothold(), true);
            }
            cursor = step2.point();
            currentFoothold = step2.foothold();
            state = step2.state();
        }
        return new PostLandingJump(landing, cursor, currentFoothold, false);
    }

    private static Point roundedAirPosition(BotMovementState entry) {
        return new Point((int) Math.round(entry.physX), (int) Math.round(entry.physY));
    }

    static void applySwimMotion(BotMovementState entry) {
        double d;
        Character bot = entry.bot;
        MapleMap map = bot.getMap();
        Point pos = bot.getPosition();
        double t = tickS();
        if (!entry.swimming) {
            entry.physX = pos.x;
            entry.physY = pos.y;
            entry.airVelX = 0;
            entry.airSteerVelX = 0.0d;
            entry.fixedAirArc = false;
            entry.downJumpPending = false;
            entry.downJumpGracePeriodMS = 0L;
        } else if (Math.abs(entry.physX - pos.x) > 2.0d || Math.abs(entry.physY - pos.y) > 2.0d) {
            entry.physX = pos.x;
            entry.physY = pos.y;
        }
        double vx = entry.hspeed;
        double vy = entry.velY;
        if (entry.swimJumpRequested) {
            float burst = cfg.SWIM_JUMP_BURST_PXS;
            if (entry.movementProfile != null) {
                burst *= (float) entry.movementProfile.speedMultiplier();
            }
            vy = -burst;
            entry.swimJumpRequested = false;
        }
        if (entry.swimMoveDir != 0) {
            double accelStep = cfg.SWIM_ACCEL_PXS2 * t * Integer.signum(entry.swimMoveDir);
            vx += accelStep;
        }
        double dragRetention = Math.max(0.0d, 1.0d - (cfg.SWIM_FRICTION_HZ * t));
        double vx2 = vx * dragRetention;
        double vy2 = (vy * dragRetention) + (cfg.SWIM_GRAVITY_PXS2 * t);
        if (entry.swimVerticalHold < 0) {
            vy2 -= cfg.SWIM_UP_THRUST_PXS2 * t;
        } else if (entry.swimVerticalHold > 0) {
            vy2 += cfg.SWIM_DOWN_THRUST_PXS2 * t;
        }
        double vx3 = Math.max(-cfg.SWIM_MAX_SPEED_PXS, Math.min(cfg.SWIM_MAX_SPEED_PXS, vx2));
        if (entry.swimMoveDir != 0) {
            double cap = cfg.SWIM_VEL_PXS;
            if (vx3 > cap && entry.swimMoveDir > 0) {
                vx3 = cap;
            }
            if (vx3 < (-cap) && entry.swimMoveDir < 0) {
                vx3 = -cap;
            }
        }
        switch (Integer.signum(entry.swimVerticalHold)) {
            case -1:
                d = cfg.SWIM_UP_MAX_SINK_PXS;
                break;
            case 1:
                d = cfg.SWIM_DOWN_MAX_SPEED_PXS;
                break;
            default:
                d = cfg.SWIM_FREE_MAX_SINK_PXS;
                break;
        }
        double sinkCap = d;
        double vy3 = Math.max(-cfg.SWIM_MAX_SPEED_PXS, Math.min(sinkCap, vy2));
        double nextX = entry.physX + (vx3 * t);
        double nextY = entry.physY + (vy3 * t);
        boolean landed = false;
        Foothold landingFoothold = null;
        double landingDeltaX = 0.0d;
        double landingDeltaY = 0.0d;
        Point prevPt = new Point((int) Math.round(entry.physX), (int) Math.round(entry.physY));
        Point nextPt = new Point((int) Math.round(nextX), (int) Math.round(nextY));
        AirCollision collision = resolveAirCollision(map, prevPt, nextPt);
        if (collision.type() == AirCollisionType.LAND) {
            nextX = collision.point().x;
            nextY = collision.point().y;
            vy3 = 0.0d;
            landed = true;
            landingFoothold = collision.foothold();
            landingDeltaX = nextX - prevPt.x;
            landingDeltaY = nextY - prevPt.y;
        } else if (collision.type() == AirCollisionType.WALL) {
            nextX = collision.point().x;
            vx3 = 0.0d;
        }
        if (entry.swimMoveDir > 0) {
            entry.facingDir = 1;
        } else if (entry.swimMoveDir < 0) {
            entry.facingDir = -1;
        }
        if (landed) {
            entry.swimming = false;
            landOnGround(entry, bot, new Point((int) Math.round(nextX), (int) Math.round(nextY)), landingFoothold, landingDeltaX, landingDeltaY);
            return;
        }
        entry.hspeed = vx3;
        entry.velY = (float) vy3;
        entry.physX = nextX;
        entry.physY = nextY;
        entry.crouching = false;
        entry.movementVelX = (int) Math.round(vx3);
        entry.movementVelY = (int) Math.round(vy3);
        entry.swimming = true;
        entry.inAir = true;
        bot.setPosition(new Point((int) Math.round(nextX), (int) Math.round(nextY)));
    }

    private static double clampMagnitude(double value, double maxAbs) {
        if (value > maxAbs) {
            return maxAbs;
        }
        if (value < (-maxAbs)) {
            return -maxAbs;
        }
        return value;
    }

    private static void applyAirSteering(BotMovementState entry, MapleMap map, int steerDir) {
        if (steerDir == 0) {
            return;
        }
        double t = tickS();
        double fs = mapGroundSlipScale(map, entry.movementProfile);
        double band = (walkSpeedPerTick(entry.movementProfile) * fs) / cfg.AIR_INPUT_BAND_DIVISOR;
        double total = entry.airVelX + entry.airSteerVelX;
        double inDir = total * steerDir;
        if (inDir < band) {
            entry.airSteerVelX = (Math.min(band, inDir + (((cfg.AIR_CONTROL_ACCEL_PXSS * fs) * t) * t)) * steerDir) - entry.airVelX;
        }
        entry.facingDir = steerDir > 0 ? 1 : -1;
    }

    private static void applyAirDrag(BotMovementState entry, MapleMap map) {
        double total = entry.airVelX + entry.airSteerVelX;
        if (total == 0.0d) {
            return;
        }
        double t = tickS();
        double fs = mapGroundSlipScale(map, entry.movementProfile);
        boolean terminalFall = entry.velY >= maxFallPerTick();
        double drag = (terminalFall ? cfg.AIR_DRAG_TERMINAL_PXSS : cfg.AIR_DRAG_PXSS) * fs * t * t;
        double next = total > 0.0d ? Math.max(0.0d, total - drag) : Math.min(0.0d, total + drag);
        entry.airSteerVelX = next - entry.airVelX;
    }

    private static Point advanceAirbornePosition(BotMovementState entry, Character bot) {
        entry.physX += entry.airVelX + entry.airSteerVelX;
        float gravity = gravityPerTick();
        entry.physY += entry.velY + (0.5f * gravity);
        entry.velY = Math.min(entry.velY + gravity, maxFallPerTick());
        if (entry.physY < entry.fallPeakPhysY) {
            entry.fallPeakPhysY = entry.physY;
        }
        return roundedAirPosition(entry);
    }

    private static void applyAirbornePosition(BotMovementState entry, Character bot, Point position) {
        bot.setPosition(position);
        entry.inAir = true;
        entry.climbing = false;
        entry.climbRope = null;
        entry.crouching = false;
        int facingDir = entry.facingDir;
        setMovementVelocity(entry, velocityFromDeltaX(entry.airVelX), velocityFromAirStep(entry.velY));
        entry.facingDir = facingDir;
        syncCharacterState(entry);
    }

    static AirborneStepResult stepAirborne(BotMovementState entry, Character bot) {
        if (entry.moveDir != 0) {
            applyAirSteering(entry, bot.getMap(), entry.moveDir);
        } else if (!entry.fixedAirArc) {
            applyAirDrag(entry, bot.getMap());
        }
        if (entry.pendingFlashJump && entry.velY >= flashJumpTriggerVelY(entry)) {
            int dir = entry.airVelX != 0 ? Integer.signum(entry.airVelX) : entry.facingDir >= 0 ? 1 : -1;
            entry.airVelX = Math.round(dir * flashJumpHPerTick() * entry.flashJumpScale);
            entry.airSteerVelX = 0.0d;
            entry.velY = flashJumpVPerTick() * entry.flashJumpScale;
            entry.fixedAirArc = true;
            entry.pendingFlashJump = false;
            entry.flashJumpFired = true;
        }
        Point previousPos = roundedAirPosition(entry);
        Point nextPos = advanceAirbornePosition(entry, bot);
        AirCollision collision = resolveAirCollision(bot.getMap(), previousPos, nextPos);
        if (collision.type() == AirCollisionType.WALL) {
            collideWithAirWall(entry, bot, collision.point());
            return AirborneStepResult.WALL;
        }
        if (collision.type() == AirCollisionType.CEILING) {
            collideWithAirCeiling(entry, bot, collision.point());
            return AirborneStepResult.CEILING;
        }
        if (collision.type() == AirCollisionType.LAND && (canLand(entry) || forbidFallDownLanding(collision))) {
            landOnGround(entry, bot, collision.point(), collision.foothold(), nextPos.x - previousPos.x, nextPos.y - previousPos.y);
            return AirborneStepResult.LANDED;
        }
        applyAirbornePosition(entry, bot, nextPos);
        return AirborneStepResult.CONTINUE;
    }

    private static void collideWithAirWall(BotMovementState entry, Character bot, Point collisionPoint) {
        entry.airVelX = 0;
        entry.airSteerVelX = 0.0d;
        entry.fixedAirArc = false;
        entry.physX = collisionPoint.x;
        entry.physY = collisionPoint.y;
        bot.setPosition(collisionPoint);
        entry.inAir = true;
        entry.climbing = false;
        entry.climbRope = null;
        entry.crouching = false;
        setMovementVelocity(entry, 0, velocityFromAirStep(entry.velY));
        syncCharacterState(entry);
    }

    private static void collideWithAirCeiling(BotMovementState entry, Character bot, Point collisionPoint) {
        entry.velY = 0.0f;
        entry.fixedAirArc = false;
        entry.physX = collisionPoint.x;
        entry.physY = collisionPoint.y;
        bot.setPosition(collisionPoint);
        entry.inAir = true;
        entry.climbing = false;
        entry.climbRope = null;
        entry.crouching = false;
        setMovementVelocity(entry, velocityFromDeltaX(entry.airVelX), 0);
        syncCharacterState(entry);
    }

    static MovementSnapshot movementSnapshot(BotMovementState entry) {
        int stance = resolveStance(entry);
        if (entry.bot != null && entry.bot.getStance() != stance) {
            entry.bot.setStance(stance);
        }
        return new MovementSnapshot(entry.movementVelX, entry.movementVelY, broadcastStance(entry, stance));
    }

    private static int broadcastStance(BotMovementState entry, int baseStance) {
        if (System.currentTimeMillis() >= entry.alertedUntilMs) {
            return baseStance;
        }
        if (baseStance == 4) {
            return TOP_EXIT_X_TOL;
        }
        if (baseStance == 5) {
            return 9;
        }
        return baseStance;
    }

    static int resolveStance(BotMovementState entry) {
        Character bot = entry.bot;
        if (bot != null && bot.getHp() <= 0) {
            return resolveDeadStance(entry);
        }
        if (entry.climbing) {
            if (entry.climbRope != null && entry.climbRope.isLadder()) {
                return 14;
            }
            return 16;
        }
        if (entry.swimming) {
            if (entry.facingDir >= 0) {
                return WALK_GAP_PX;
            }
            return 13;
        }
        if (entry.crouching) {
            return entry.facingDir >= 0 ? 10 : 11;
        }
        if (entry.inAir) {
            if (entry.facingDir >= 0) {
                return GROUND_BUCKET_SHIFT;
            }
            return 7;
        }
        if (entry.moveDir > 0) {
            return REGION_STITCH_GAP_PX;
        }
        if (entry.moveDir < 0) {
            return 3;
        }
        if (entry.groundBrakeDir != 0) {
            if (entry.groundBrakeDir > 0) {
                return REGION_STITCH_GAP_PX;
            }
            return 3;
        }
        return resolveIdleGroundStance(entry);
    }

    static int resolveIdleGroundStance(BotMovementState entry) {
        return entry.facingDir >= 0 ? 4 : 5;
    }

    static int resolveDeadStance(BotMovementState entry) {
        return entry.facingDir >= 0 ? 18 : 19;
    }

    static boolean isStandingStance(int stance) {
        return CharacterStance.isStanding(stance);
    }

    static void syncCharacterState(BotMovementState entry) {
        Character bot = entry.bot;
        if (bot == null) {
            return;
        }
        bot.setStance(resolveStance(entry));
    }

    static float calculateMaxJumpHeight() {
        return calculateMaxJumpHeight(BotMovementProfile.base());
    }

    static float calculateMaxJumpHeight(BotMovementProfile profile) {
        float jumpForce = jumpForcePerTick(profile);
        return (jumpForce * jumpForce) / (2.0f * gravityPerTick());
    }

    static int maxJumpHorizontalTravel(MapleMap map) {
        return maxJumpHorizontalTravel(map, BotMovementProfile.base());
    }

    static int maxJumpHorizontalTravel(MapleMap map, BotMovementProfile profile) {
        return maxHorizontalTravel(map, profile, jumpForcePerTick(profile));
    }

    static int maxRopeJumpHorizontalTravel(MapleMap map) {
        return maxRopeJumpHorizontalTravel(map, BotMovementProfile.base());
    }

    static int maxRopeJumpHorizontalTravel(MapleMap map, BotMovementProfile profile) {
        return maxHorizontalTravel(map, profile, ropeJumpForcePerTick(profile));
    }

    static int maxRopeGrabSimulationHorizontalTravel(MapleMap map, BotMovementProfile profile) {
        int maxTicks = Math.max(1, 1500 / cfg.TICK_MS);
        return walkStep(map, profile) * maxTicks;
    }

    static Point simulateRopeJumpGrab(MapleMap map, Point from, int stepX, Rope targetRope) {
        return simulateRopeJumpGrab(map, from, stepX, targetRope, BotMovementProfile.base());
    }

    static Point simulateRopeJumpGrab(MapleMap map, Point from, int stepX, Rope targetRope, BotMovementProfile profile) {
        return simulateRopeGrab(map, from, -ropeJumpForcePerTick(profile), stepX, targetRope, 0L);
    }

    static Point simulateGroundJumpRopeGrab(MapleMap map, Point from, int stepX, Rope targetRope) {
        return simulateGroundJumpRopeGrab(map, from, stepX, targetRope, BotMovementProfile.base());
    }

    static Point simulateGroundJumpRopeGrab(MapleMap map, Point from, int stepX, Rope targetRope, BotMovementProfile profile) {
        return simulateRopeGrab(map, from, -jumpForcePerTick(profile), stepX, targetRope, 0L);
    }

    static Point simulateDownJumpRopeGrab(MapleMap map, Point from, Rope targetRope) {
        return simulateRopeGrab(map, from, -downJumpForcePerTick(), 0, targetRope, cfg.DOWN_JUMP_GRACE_MS);
    }

    static boolean canReachRopeFromGround(MapleMap map, Point from, Rope rope) {
        return canReachRopeFromGround(map, from, rope, BotMovementProfile.base());
    }

    static boolean canReachRopeFromGround(MapleMap map, Point from, Rope rope, BotMovementProfile profile) {
        int dx = Math.abs(rope.x() - from.x);
        if (dx <= cfg.ROPE_GRAB_X && from.y >= firstClimbableY(rope) && from.y <= rope.bottomY()) {
            return true;
        }
        if (rope.topY() >= from.y) {
            return false;
        }
        int jumpReach = (int) Math.ceil(calculateMaxJumpHeight(profile));
        int dropToRopeBottom = Math.max(0, rope.bottomY() - from.y);
        return rope.bottomY() >= from.y - jumpReach && dx <= maxHorizontalTravelWithDrop(map, profile, jumpForcePerTick(profile), dropToRopeBottom);
    }

    static boolean canStartDownJump(MapleMap map, Point from) {
        Foothold foothold = findGroundFoothold(map, from);
        return (foothold == null || foothold.isForbidFallDown()) ? false : true;
    }

    private static boolean forbidFallDownLanding(AirCollision collision) {
        return collision.foothold() != null && collision.foothold().isForbidFallDown();
    }

    static JumpLanding simulateJumpLanding(MapleMap map, Point from, int stepX) {
        return simulateJumpLanding(map, from, stepX, BotMovementProfile.base());
    }

    static JumpLanding simulateJumpLanding(MapleMap map, Point from, int stepX, BotMovementProfile profile) {
        return simulateLanding(map, from, -jumpForcePerTick(profile), stepX, 0L);
    }

    static PostLandingJump simulateJumpLandingWithPostLandingTicks(MapleMap map, Point from, int stepX, BotMovementProfile profile, int postLandingTicks) {
        JumpLanding landing = simulateJumpLanding(map, from, stepX, profile);
        if (landing == null) {
            return null;
        }
        return simulatePostLandingGroundTicks(map, landing, Integer.compare(stepX, 0), profile, postLandingTicks);
    }

    static JumpLanding simulateDownJumpLanding(MapleMap map, Point from) {
        if (!canStartDownJump(map, from)) {
            return null;
        }
        return simulateLanding(map, from, -downJumpForcePerTick(), 0, cfg.DOWN_JUMP_GRACE_MS);
    }

    static JumpLanding simulateFallLanding(MapleMap map, Point from, int stepX) {
        return simulateLanding(map, from, 0.0f, stepX, 0L);
    }

    static JumpLanding simulateRopeJumpLanding(MapleMap map, Point from, int stepX) {
        return simulateRopeJumpLanding(map, from, stepX, BotMovementProfile.base());
    }

    static JumpLanding simulateRopeJumpLanding(MapleMap map, Point from, int stepX, BotMovementProfile profile) {
        return simulateLanding(map, from, -ropeJumpForcePerTick(profile), stepX, 0L);
    }

    static int estimateJumpLandingTimeMs(MapleMap map, Point from, int stepX) {
        return estimateJumpLandingTimeMs(map, from, stepX, BotMovementProfile.base());
    }

    static int estimateJumpLandingTimeMs(MapleMap map, Point from, int stepX, BotMovementProfile profile) {
        return estimateLandingTimeMs(map, from, -jumpForcePerTick(profile), stepX, 0L);
    }

    static int estimateDownJumpLandingTimeMs(MapleMap map, Point from) {
        return estimateLandingTimeMs(map, from, -downJumpForcePerTick(), 0, cfg.DOWN_JUMP_GRACE_MS);
    }

    static int estimateFallLandingTimeMs(MapleMap map, Point from, int stepX) {
        return estimateLandingTimeMs(map, from, 0.0f, stepX, 0L);
    }

    static int estimateRopeJumpLandingTimeMs(MapleMap map, Point from, int stepX) {
        return estimateRopeJumpLandingTimeMs(map, from, stepX, BotMovementProfile.base());
    }

    static int estimateRopeJumpLandingTimeMs(MapleMap map, Point from, int stepX, BotMovementProfile profile) {
        return estimateLandingTimeMs(map, from, -ropeJumpForcePerTick(profile), stepX, 0L);
    }

    static int estimateGroundJumpRopeGrabTimeMs(MapleMap map, Point from, int stepX, Rope targetRope) {
        return estimateGroundJumpRopeGrabTimeMs(map, from, stepX, targetRope, BotMovementProfile.base());
    }

    static int estimateGroundJumpRopeGrabTimeMs(MapleMap map, Point from, int stepX, Rope targetRope, BotMovementProfile profile) {
        return estimateRopeGrabTimeMs(map, from, -jumpForcePerTick(profile), stepX, targetRope, 0L);
    }

    static int estimateDownJumpRopeGrabTimeMs(MapleMap map, Point from, Rope targetRope) {
        return estimateRopeGrabTimeMs(map, from, -downJumpForcePerTick(), 0, targetRope, cfg.DOWN_JUMP_GRACE_MS);
    }

    static int estimateRopeJumpGrabTimeMs(MapleMap map, Point from, int stepX, Rope targetRope) {
        return estimateRopeJumpGrabTimeMs(map, from, stepX, targetRope, BotMovementProfile.base());
    }

    static int estimateRopeJumpGrabTimeMs(MapleMap map, Point from, int stepX, Rope targetRope, BotMovementProfile profile) {
        return estimateRopeGrabTimeMs(map, from, -ropeJumpForcePerTick(profile), stepX, targetRope, 0L);
    }

    private static AirCollision resolveAirCollision(MapleMap map, Point previousPos, Point nextPos) {
        if (map == null || map.getFootholds() == null || previousPos == null || nextPos == null) {
            return AirCollision.none();
        }
        AirCollision wall = findWallCollision(map, previousPos, nextPos);
        AirCollision ceiling = findCeilingCollision(map, previousPos, nextPos);
        AirCollision landing = findGroundCollision(map, previousPos, nextPos);
        AirCollision best = AirCollision.none();
        if (wall.type() != AirCollisionType.NONE) {
            best = wall;
        }
        if (ceiling.type() != AirCollisionType.NONE && ceiling.progress() < best.progress()) {
            best = ceiling;
        }
        if (landing.type() != AirCollisionType.NONE && landing.progress() < best.progress()) {
            best = landing;
        }
        return best;
    }

    private static void launchAirborne(BotMovementState entry, Character bot, Point position, float initialVelY, int airVelX, boolean climbUpIntent) {
        entry.climbing = false;
        entry.climbRope = null;
        entry.inAir = true;
        entry.crouching = false;
        entry.physX = position.x;
        entry.physY = position.y;
        entry.velY = initialVelY;
        stopGroundMotion(entry);
        entry.climbUpIntent = climbUpIntent;
        clearRopeEntryIntent(entry);
        entry.airVelX = airVelX;
        entry.airSteerVelX = 0.0d;
        entry.fixedAirArc = false;
        entry.downJumpPending = false;
        entry.pendingFlashJump = false;
        entry.flashJumpFired = false;
        entry.moveDir = 0;
        entry.groundBrakeDir = 0;
        setMovementVelocity(entry, velocityFromDeltaX(airVelX), velocityFromAirStep(initialVelY));
        syncCharacterState(entry);
    }

    private static boolean resolveClimbBoundary(BotMovementState entry, Character bot, Rope rope, int candidateY) {
        if (candidateY <= rope.topY()) {
            Point landing = findTopLandingPoint(bot, rope, candidateY);
            if (landing != null) {
                landOnGround(entry, bot, landing);
                return true;
            }
            setClimbPosition(entry, bot, rope, firstClimbableY(rope));
            return true;
        }
        if (candidateY > rope.bottomY()) {
            beginFall(entry, bot, 0);
            return true;
        }
        return false;
    }

    static Point findTopExitLanding(MapleMap map, Rope rope) {
        int delta;
        if (map == null || rope == null) {
            return null;
        }
        int topY = rope.topY();
        int probeY = (topY - TOP_EXIT_UP_TOL) - 1;
        int lowBound = topY - TOP_EXIT_UP_TOL;
        int highBound = topY + TOP_EXIT_DOWN_TOL;
        Point best = null;
        int bestDelta = Integer.MAX_VALUE;
        for (int x : new int[]{rope.x(), rope.x() - TOP_EXIT_X_TOL, rope.x() + TOP_EXIT_X_TOL}) {
            Point ground = pointBelowIndexed(map, new Point(x, probeY));
            if (ground != null && ground.y >= lowBound && ground.y <= highBound && (delta = Math.abs(ground.y - topY)) < bestDelta) {
                best = ground;
                bestDelta = delta;
            }
        }
        return best;
    }

    private static Point findTopLandingPoint(Character bot, Rope rope, int candidateY) {
        MapleMap map = bot.getMap();
        if (map == null) {
            return null;
        }
        return findTopExitLanding(map, rope);
    }

    static int firstClimbableY(Rope rope) {
        return Math.min(rope.bottomY(), rope.topY() + 1);
    }

    private static void setClimbPosition(BotMovementState entry, Character bot, Rope rope, int y) {
        Point position = new Point(rope.x(), y);
        bot.setPosition(position);
        entry.climbing = true;
        entry.climbRope = rope;
        entry.inAir = false;
        entry.crouching = false;
        entry.climbUpIntent = false;
        entry.velY = 0.0f;
        entry.airVelX = 0;
        entry.airSteerVelX = 0.0d;
        entry.fixedAirArc = false;
        entry.physX = position.x;
        entry.physY = position.y;
        clearRopeEntryIntent(entry);
        entry.downJumpPending = false;
        stopGroundMotion(entry);
        setMovementVelocity(entry, 0, 0);
        syncCharacterState(entry);
    }

    private static void clearRopeEntryIntent(BotMovementState entry) {
        entry.ropeEntryPending = false;
        entry.ropeEntryRope = null;
        entry.ropeEntryY = 0;
    }

    private static void clearMovementState(BotMovementState entry, Point position) {
        entry.inAir = false;
        entry.climbing = false;
        entry.climbRope = null;
        entry.crouching = false;
        entry.velY = 0.0f;
        entry.hspeed = 0.0d;
        entry.physX = position.x;
        entry.physY = position.y;
        entry.groundPhysicsCarryMs = 0.0d;
        entry.airVelX = 0;
        entry.airSteerVelX = 0.0d;
        entry.fixedAirArc = false;
        entry.pendingFlashJump = false;
        entry.flashJumpFired = false;
        entry.wasMovingX = false;
        entry.moveDir = 0;
        entry.groundBrakeDir = 0;
        entry.climbUpIntent = false;
        entry.blockedRopeGrab = null;
        entry.ropeGrabCooldownMs = 0;
        entry.downJumpPending = false;
        entry.downJumpGracePeriodMS = 0L;
        clearRopeEntryIntent(entry);
        setMovementVelocity(entry, 0, 0);
    }

    private static void setMovementVelocity(BotMovementState entry, int velX, int velY) {
        entry.movementVelX = velX;
        entry.movementVelY = velY;
        if (velX != 0) {
            entry.facingDir = velX > 0 ? 1 : -1;
        }
    }

    private static int velocityFromAirStep(float airVelPerTick) {
        return Math.round(airVelPerTick * (1000.0f / cfg.TICK_MS));
    }

    private static GroundTravelState applyGroundDisplacement(MapleMap map, Foothold foothold, int desiredDir, GroundTravelState state, BotMovementProfile profile) {
        GroundStepCounter counter = groundPhysicsSteps(state.carryMs(), map);
        if (counter.steps() == 0) {
            return state;
        }
        double physX = state.physX();
        double hspeed = state.hspeed();
        double slipScale = mapGroundSlipScale(map, profile);
        for (int i = 0; i < counter.steps(); i++) {
            hspeed = applyGroundPhysicsStep(hspeed, foothold, desiredDir, profile, slipScale);
            physX += hspeed;
        }
        return new GroundTravelState(physX, hspeed, counter.carryMs());
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$GroundStepCounter.class */
    private static final class GroundStepCounter {
        private final int steps;
        private final double carryMs;

        private GroundStepCounter(int steps, double carryMs) {
            this.steps = steps;
            this.carryMs = carryMs;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public int steps() {
            return this.steps;
        }

        public double carryMs() {
            return this.carryMs;
        }
    }

    private static GroundStepCounter groundPhysicsSteps(double carryMs, MapleMap map) {
        double nextCarryMs = carryMs + cfg.TICK_MS;
        int steps = (int) (nextCarryMs / CLIENT_GROUND_STEP_MS);
        return new GroundStepCounter(steps, nextCarryMs - (steps * CLIENT_GROUND_STEP_MS));
    }

    private static double applyGroundPhysicsStep(double hspeed, Foothold foothold, int desiredDir, BotMovementProfile profile, double slipScale) {
        double hforce = desiredDir * maxHForcePerClientStep(profile);
        if (hforce == 0.0d && Math.abs(hspeed) < 0.1d) {
            return 0.0d;
        }
        if (slipScale < 1.0d) {
            return applySlipperyGroundStep(hspeed, desiredDir, profile, slipScale);
        }
        double inertia = hspeed / cfg.GROUNDSLIP;
        double slope = clampedSlope(foothold);
        double drag = (cfg.FRICTION + (cfg.SLOPEFACTOR * (1.0d + (slope * (-inertia))))) * inertia;
        return hspeed + ((hforce - drag) * slipScale);
    }

    private static double applySlipperyGroundStep(double hspeed, int desiredDir, BotMovementProfile profile, double fs) {
        if (desiredDir != 0) {
            double dv = cfg.SLIP_WALK_ACCEL_PXSS * fs * CLIENT_GROUND_STEP_S * CLIENT_GROUND_STEP_S;
            double cap = maxHSpeedPerClientStep(profile);
            return Math.clamp(hspeed + (desiredDir * dv), -cap, cap);
        }
        double dv2 = cfg.SLIP_GLIDE_DECEL_PXSS * fs * CLIENT_GROUND_STEP_S * CLIENT_GROUND_STEP_S;
        return hspeed - Math.copySign(Math.min(Math.abs(hspeed), dv2), hspeed);
    }

    private static double clampedSlope(Foothold foothold) {
        if (foothold == null) {
            return 0.0d;
        }
        return Math.clamp(foothold.slope(), -0.5d, 0.5d);
    }

    static boolean isWalkableEndpointStep(int dx, int dy) {
        return dx <= WALK_GAP_PX && dy <= cfg.MAX_SNAP_DROP && dy >= (-cfg.MAX_SLOPE_UP);
    }

    private static double mapGroundSlipScale(MapleMap map) {
        float fs = map != null ? map.getFootholdSpeed() : 0.0f;
        if (fs <= 0.0f || fs >= 1.0f) {
            return 1.0d;
        }
        return fs;
    }

    private static double mapGroundSlipScale(MapleMap map, BotMovementProfile profile) {
        if (profileOrBase(profile).snowShoes()) {
            return 1.0d;
        }
        return mapGroundSlipScale(map);
    }

    static int counterStrafeBrakeDir(MapleMap map, BotMovementProfile profile, double hspeed) {
        double fs = mapGroundSlipScale(map, profile);
        if (fs >= 1.0d) {
            return 0;
        }
        double brakePerTick = cfg.SLIP_WALK_ACCEL_PXSS * fs * CLIENT_GROUND_STEP_S * CLIENT_GROUND_STEP_S * Math.max(1.0d, cfg.TICK_MS / CLIENT_GROUND_STEP_MS);
        if (Math.abs(hspeed) > brakePerTick) {
            return hspeed > 0.0d ? -1 : 1;
        }
        return 0;
    }

    static int slipperyStopDir(MapleMap map, BotMovementProfile profile, Point position, Foothold foothold, GroundTravelState state) {
        int brakeDir = counterStrafeBrakeDir(map, profile, state.hspeed());
        if (brakeDir == 0) {
            return 0;
        }
        GroundTravelState s = state;
        Point cursor = position;
        Foothold fh = foothold;
        for (int i = 0; i < POST_LANDING_BRAKE_TICK_CAP && Math.abs(s.hspeed()) > 0.0d; i++) {
            GroundStepResult step = simulateGroundMotion(map, cursor, fh, 0, s, profile);
            if (step.lostGround()) {
                return brakeDir;
            }
            cursor = step.point();
            fh = step.foothold();
            s = step.state();
        }
        return 0;
    }

    static int slipperyApproachDir(MapleMap map, BotMovementProfile profile, double hspeed, int dxToTarget) {
        return slipperyApproachDir(map, profile, hspeed, dxToTarget, 0);
    }

    static int slipperyApproachDir(MapleMap map, BotMovementProfile profile, double hspeed, int dxToTarget, int overshootSlackPx) {
        int towardDir = Integer.signum(dxToTarget);
        double fs = mapGroundSlipScale(map, profile);
        if (towardDir == 0 || fs >= 1.0d) {
            return towardDir;
        }
        double dvBrake = cfg.SLIP_WALK_ACCEL_PXSS * fs * CLIENT_GROUND_STEP_S * CLIENT_GROUND_STEP_S;
        double dvGlide = cfg.SLIP_GLIDE_DECEL_PXSS * fs * CLIENT_GROUND_STEP_S * CLIENT_GROUND_STEP_S;
        double cap = maxHSpeedPerClientStep(profile);
        int stepsPerTick = Math.max(1, (int) Math.ceil(cfg.TICK_MS / CLIENT_GROUND_STEP_MS));
        double brakeReleaseSpeed = dvBrake * stepsPerTick;
        double v = hspeed * towardDir;
        double traveled = 0.0d;
        for (int i = 0; i < stepsPerTick; i++) {
            v = Math.min(v + dvBrake, cap);
            traveled += v;
        }
        while (v > brakeReleaseSpeed) {
            v -= dvBrake;
            traveled += v;
        }
        while (v > 0.0d) {
            v -= dvGlide;
            traveled += Math.max(v, 0.0d);
        }
        if (traveled < Math.abs(dxToTarget) + Math.max(0, overshootSlackPx)) {
            return towardDir;
        }
        return counterStrafeBrakeDir(map, profile, hspeed);
    }

    static boolean slipperyGround(MapleMap map) {
        return mapGroundSlipScale(map) < 1.0d;
    }

    private static double maxHForcePerClientStep(BotMovementProfile profile) {
        return profileOrBase(profile).hForcePxs() * CLIENT_GROUND_STEP_S;
    }

    private static double maxHSpeedPerClientStep(BotMovementProfile profile) {
        return (maxHForcePerClientStep(profile) * cfg.GROUNDSLIP) / (cfg.FRICTION + cfg.SLOPEFACTOR);
    }

    private static double walkSpeedPerTick(BotMovementProfile profile) {
        return maxHSpeedPerClientStep(profile) * Math.max(1.0d, cfg.TICK_MS / CLIENT_GROUND_STEP_MS);
    }

    static int carriedAirVelX(MapleMap map, BotMovementState entry) {
        return (int) Math.round(tickDeltaFromGroundHSpeed(map, entry.hspeed, entry.movementProfile));
    }

    private static int maxHorizontalTravel(MapleMap map, BotMovementProfile profile, float launchSpeedPerTick) {
        int airtimeTicks = Math.max(1, (int) Math.ceil((2.0f * launchSpeedPerTick) / gravityPerTick()));
        return walkStep(map, profile) * airtimeTicks;
    }

    private static int maxHorizontalTravelWithDrop(MapleMap map, BotMovementProfile profile, float launchSpeedPerTick, int dropPx) {
        float g = gravityPerTick();
        float tUp = launchSpeedPerTick / g;
        float apex = (launchSpeedPerTick * launchSpeedPerTick) / (2.0f * g);
        float tDown = (float) Math.sqrt((2.0f * (apex + Math.max(0, dropPx))) / g);
        int airtimeTicks = Math.max(1, (int) Math.ceil(tUp + tDown));
        return walkStep(map, profile) * airtimeTicks;
    }

    private static AirCollision findGroundCollision(MapleMap map, Point previousPos, Point nextPos) {
        if (nextPos.y < previousPos.y) {
            return AirCollision.none();
        }
        int startX = previousPos.x;
        int endX = nextPos.x;
        int dir = Integer.compare(endX, startX);
        if (dir == 0) {
            return landingAtX(map, previousPos, nextPos, endX, 1.0d);
        }
        int steps = Math.abs(endX - startX);
        for (int i = 0; i <= steps; i++) {
            int x = startX + (dir * i);
            double progress = i / steps;
            AirCollision landing = landingAtX(map, previousPos, nextPos, x, progress);
            if (landing.type == AirCollisionType.LAND) {
                return landing;
            }
        }
        return AirCollision.none();
    }

    private static AirCollision findCeilingCollision(MapleMap map, Point previousPos, Point nextPos) {
        if (map == null || map.getFootholds() == null || nextPos.y >= previousPos.y) {
            return AirCollision.none();
        }
        AirCollision best = AirCollision.none();
        for (Foothold foothold : collisionIndex(map).collidableFromBelow()) {
            AirCollision collision = ceilingCollision(foothold, previousPos, nextPos);
            if (collision.type() == AirCollisionType.CEILING && collision.progress() < best.progress()) {
                best = collision;
            }
        }
        return best;
    }

    private static AirCollision findWallCollision(MapleMap map, Point previousPos, Point nextPos) {
        return findWallCollision(map, previousPos, nextPos, false);
    }

    private static AirCollision findGroundWallCollision(MapleMap map, Point previousPos, Point nextPos) {
        return findWallCollision(map, previousPos, nextPos, true);
    }

    private static AirCollision findWallCollision(MapleMap map, Point previousPos, Point nextPos, boolean allowWalkableGroundEndpoint) {
        if (map == null || map.getFootholds() == null) {
            return AirCollision.none();
        }
        if (previousPos.x == nextPos.x) {
            return AirCollision.none();
        }
        AirCollision best = mapSideBoundaryCollision(map, previousPos, nextPos);
        for (Foothold foothold : collisionIndex(map).collidableWalls()) {
            AirCollision collision = wallCollision(foothold, previousPos, nextPos, allowWalkableGroundEndpoint);
            if (collision.type() == AirCollisionType.WALL && collision.progress() < best.progress()) {
                best = collision;
            }
        }
        return best;
    }

    private static AirCollision mapSideBoundaryCollision(MapleMap map, Point previousPos, Point nextPos) {
        Rectangle area = map.getMapArea();
        if (area == null || area.width <= 0 || area.height <= 0 || previousPos.x == nextPos.x) {
            return AirCollision.none();
        }
        int dir = Integer.compare(nextPos.x, previousPos.x);
        int boundaryX = dir > 0 ? effectiveRightBoundaryX(map, area) : effectiveLeftBoundaryX(map, area);
        if (dir > 0 && (previousPos.x > boundaryX || nextPos.x <= boundaryX)) {
            return AirCollision.none();
        }
        if (dir < 0 && (previousPos.x < boundaryX || nextPos.x >= boundaryX)) {
            return AirCollision.none();
        }
        double progress = (boundaryX - previousPos.x) / (nextPos.x - previousPos.x);
        if (progress < 0.0d || progress > 1.0d) {
            return AirCollision.none();
        }
        double yAtBoundary = previousPos.y + ((nextPos.y - previousPos.y) * progress);
        return new AirCollision(AirCollisionType.WALL, new Point(boundaryX, (int) Math.round(yAtBoundary)), null, progress);
    }

    private static int effectiveLeftBoundaryX(MapleMap map, Rectangle area) {
        if (!hasUsableFootholdXBounds(map)) {
            return area.x;
        }
        int footholdMinX = map.getFootholds().getMinDropX();
        if (isSyntheticMapArea(area)) {
            return footholdMinX;
        }
        return Math.min(area.x, footholdMinX);
    }

    private static int effectiveRightBoundaryX(MapleMap map, Rectangle area) {
        if (!hasUsableFootholdXBounds(map)) {
            return area.x + area.width;
        }
        int footholdMaxX = map.getFootholds().getMaxDropX();
        if (isSyntheticMapArea(area)) {
            return footholdMaxX;
        }
        return Math.max(area.x + area.width, footholdMaxX);
    }

    private static boolean isSyntheticMapArea(Rectangle area) {
        return area.width >= SYNTHETIC_MAP_BOUND_SIZE && area.height >= SYNTHETIC_MAP_BOUND_SIZE;
    }

    private static boolean hasUsableFootholdXBounds(MapleMap map) {
        return map.getFootholds() != null && map.getFootholds().getMinDropX() < map.getFootholds().getMaxDropX();
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotPhysicsEngine$FootholdCollisionIndex.class */
    private static final class FootholdCollisionIndex {
        private final List<Foothold> collidableWalls;
        private final List<Foothold> collidableFromBelow;
        private final int bucketMinX;
        private final Foothold[][] groundBuckets;

        private FootholdCollisionIndex(List<Foothold> collidableWalls, List<Foothold> collidableFromBelow, int bucketMinX, Foothold[][] groundBuckets) {
            this.collidableWalls = collidableWalls;
            this.collidableFromBelow = collidableFromBelow;
            this.bucketMinX = bucketMinX;
            this.groundBuckets = groundBuckets;
        }

        public final String toString() {
            return getClass().getSimpleName();
        }

        public final int hashCode() {
            return System.identityHashCode(this);
        }

        public final boolean equals(Object o) {
            return this == o;
        }

        public List<Foothold> collidableWalls() {
            return this.collidableWalls;
        }

        public List<Foothold> collidableFromBelow() {
            return this.collidableFromBelow;
        }

        public int bucketMinX() {
            return this.bucketMinX;
        }

        public Foothold[][] groundBuckets() {
            return this.groundBuckets;
        }

        Foothold[] groundBucketAt(int x) {
            int b = (x - this.bucketMinX) >> BotPhysicsEngine.GROUND_BUCKET_SHIFT;
            return (b < 0 || b >= this.groundBuckets.length) ? BotPhysicsEngine.NO_FOOTHOLDS : this.groundBuckets[b];
        }
    }

    private static FootholdCollisionIndex collisionIndex(MapleMap map) {
        FootholdTree tree = map != null ? map.getFootholds() : null;
        if (tree == null) {
            return UNINDEXABLE;
        }
        return COLLISION_INDEX.computeIfAbsent(tree, t -> {
            Foothold[][] footholdArr;
            List<Foothold> all = t.getAllFootholds();
            if (all == null) {
                return UNINDEXABLE;
            }
            Map<Integer, Foothold> byId = new HashMap<>(all.size());
            for (Foothold fh : all) {
                byId.put(Integer.valueOf(fh.getId()), fh);
            }
            Set<Integer> fromBelowIds = BotNavigationGraphProvider.classifyCollidableFromBelowFootholds(byId);
            List<Foothold> walls = new ArrayList<>();
            List<Foothold> ground = new ArrayList<>();
            List<Foothold> fromBelow = new ArrayList<>();
            int minX = Integer.MAX_VALUE;
            int maxX = Integer.MIN_VALUE;
            for (Foothold fh2 : all) {
                if (fh2.isWall()) {
                    if (Foothold.isCollidableWall(fh2, byId)) {
                        walls.add(fh2);
                    }
                } else {
                    ground.add(fh2);
                    minX = Math.min(minX, Math.min(fh2.getX1(), fh2.getX2()));
                    maxX = Math.max(maxX, Math.max(fh2.getX1(), fh2.getX2()));
                    if (fromBelowIds.contains(Integer.valueOf(fh2.getId()))) {
                        fromBelow.add(fh2);
                    }
                }
            }
            if (ground.isEmpty()) {
                footholdArr = new Foothold[0][];
                minX = 0;
            } else {
                int bucketCount = ((maxX - minX) >> GROUND_BUCKET_SHIFT) + 1;
                List<List<Foothold>> building = new ArrayList<>(bucketCount);
                for (int i = 0; i < bucketCount; i++) {
                    building.add(null);
                }
                for (Foothold fh3 : ground) {
                    int lo = (Math.min(fh3.getX1(), fh3.getX2()) - minX) >> GROUND_BUCKET_SHIFT;
                    int hi = (Math.max(fh3.getX1(), fh3.getX2()) - minX) >> GROUND_BUCKET_SHIFT;
                    for (int b = lo; b <= hi; b++) {
                        List<Foothold> bucket = building.get(b);
                        if (bucket == null) {
                            bucket = new ArrayList<>(4);
                            building.set(b, bucket);
                        }
                        bucket.add(fh3);
                    }
                }
                footholdArr = new Foothold[bucketCount][];
                for (int i2 = 0; i2 < bucketCount; i2++) {
                    List<Foothold> bucket2 = building.get(i2);
                    if (bucket2 == null) {
                        footholdArr[i2] = NO_FOOTHOLDS;
                    } else {
                        Foothold[] sorted = (Foothold[]) bucket2.toArray(NO_FOOTHOLDS);
                        insertionSort(sorted);
                        footholdArr[i2] = sorted;
                    }
                }
            }
            return new FootholdCollisionIndex(List.copyOf(walls), List.copyOf(fromBelow), minX, footholdArr);
        });
    }

    private static void insertionSort(Foothold[] footholds) {
        for (int i = 1; i < footholds.length; i++) {
            Foothold key = footholds[i];
            int j = i - 1;
            while (j >= 0 && footholds[j].compareTo(key) > 0) {
                footholds[j + 1] = footholds[j];
                j--;
            }
            footholds[j + 1] = key;
        }
    }

    static Foothold findBelowIndexed(MapleMap map, Point p) {
        if (map == null || map.getFootholds() == null) {
            return null;
        }
        FootholdCollisionIndex index = collisionIndex(map);
        if (index == UNINDEXABLE) {
            return map.getFootholds().findBelow(p);
        }
        for (Foothold fh : index.groundBucketAt(p.x)) {
            if (fh.getX1() <= p.x && fh.getX2() >= p.x) {
                if (fh.getY1() != fh.getY2()) {
                    if (slopeYAt(fh, p.x) >= p.y) {
                        return fh;
                    }
                } else if (fh.getY1() >= p.y) {
                    return fh;
                }
            }
        }
        return null;
    }

    static Point pointBelowIndexed(MapleMap map, Point initial) {
        if (map == null) {
            return null;
        }
        if (map.getFootholds() == null || collisionIndex(map) == UNINDEXABLE) {
            return map.getPointBelow(initial);
        }
        Foothold fh = findBelowIndexed(map, initial);
        if (fh == null) {
            return null;
        }
        int dropY = fh.getY1() != fh.getY2() ? slopeYAt(fh, initial.x) : fh.getY1();
        return new Point(initial.x, dropY);
    }

    static Point findGroundPointAbove(MapleMap map, Point p, int maxRise) {
        FootholdCollisionIndex index;
        if (map == null || map.getFootholds() == null || (index = collisionIndex(map)) == UNINDEXABLE) {
            return null;
        }
        int minY = p.y - maxRise;
        for (Foothold fh : index.groundBucketAt(p.x)) {
            if (fh.getX1() <= p.x && fh.getX2() >= p.x) {
                int fy = fh.getY1() != fh.getY2() ? slopeYAt(fh, p.x) : fh.getY1();
                if (fy < p.y && fy >= minY) {
                    return new Point(p.x, fy);
                }
            }
        }
        return null;
    }

    private static int slopeYAt(Foothold fh, int x) {
        double s1 = Math.abs(fh.getY2() - fh.getY1());
        double s2 = Math.abs(fh.getX2() - fh.getX1());
        double s4 = Math.abs(x - fh.getX1());
        double alpha = Math.atan(s2 / s1);
        double beta = Math.atan(s1 / s2);
        double s5 = Math.cos(alpha) * (s4 / Math.cos(beta));
        return fh.getY2() < fh.getY1() ? fh.getY1() - ((int) s5) : fh.getY1() + ((int) s5);
    }

    private static AirCollision landingAtX(MapleMap map, Point previousPos, Point nextPos, int x, double progress) {
        int yAtX = (int) Math.round(previousPos.y + ((nextPos.y - previousPos.y) * progress));
        AirCollision landing = landingAtProbeY(map, previousPos, x, yAtX, progress, previousPos.y + 1, false);
        if (landing.type() == AirCollisionType.LAND) {
            return landing;
        }
        if (x != previousPos.x) {
            return landingAtProbeY(map, previousPos, x, yAtX, progress, previousPos.y, true);
        }
        return AirCollision.none();
    }

    private static AirCollision landingAtProbeY(MapleMap map, Point previousPos, int x, int yAtX, double progress, int probeY, boolean requireTangentFloor) {
        Point probe = new Point(x, probeY);
        Point floor = pointBelowIndexed(map, probe);
        if (floor == null) {
            return AirCollision.none();
        }
        int minY = Math.min(previousPos.y, yAtX);
        int maxY = Math.max(previousPos.y, yAtX);
        if (floor.y < minY || floor.y > maxY) {
            return AirCollision.none();
        }
        if (requireTangentFloor && floor.y != previousPos.y) {
            return AirCollision.none();
        }
        Foothold foothold = findBelowIndexed(map, probe);
        if (foothold == null) {
            return AirCollision.none();
        }
        return new AirCollision(AirCollisionType.LAND, new Point(x, floor.y), foothold, progress);
    }

    private static AirCollision wallCollision(Foothold wall, Point previousPos, Point nextPos, boolean allowWalkableGroundEndpoint) {
        int wallX = wall.getX1();
        int startX = previousPos.x;
        int endX = nextPos.x;
        if (startX == endX) {
            return AirCollision.none();
        }
        double progress = (wallX - startX) / (endX - startX);
        if (progress <= 0.0d || progress > 1.0d) {
            return AirCollision.none();
        }
        double yAtWall = previousPos.y + ((nextPos.y - previousPos.y) * progress);
        int minY = Math.min(wall.getY1(), wall.getY2());
        int maxY = Math.max(wall.getY1(), wall.getY2());
        if (yAtWall < minY || yAtWall > maxY) {
            return AirCollision.none();
        }
        if (allowWalkableGroundEndpoint && isWalkableGroundWallEndpoint(yAtWall, minY, maxY)) {
            return AirCollision.none();
        }
        int dir = Integer.compare(endX, startX);
        int safeX = wallX - dir;
        return new AirCollision(AirCollisionType.WALL, new Point(safeX, (int) Math.round(yAtWall)), wall, progress);
    }

    private static AirCollision ceilingCollision(Foothold foothold, Point previousPos, Point nextPos) {
        if (foothold.getY1() != foothold.getY2()) {
            return AirCollision.none();
        }
        int ceilingY = foothold.getY1();
        if (ceilingY > previousPos.y || ceilingY < nextPos.y) {
            return AirCollision.none();
        }
        double progress = (ceilingY - previousPos.y) / (nextPos.y - previousPos.y);
        if (progress <= 0.0d || progress > 1.0d) {
            return AirCollision.none();
        }
        double xAtCeiling = previousPos.x + ((nextPos.x - previousPos.x) * progress);
        int minX = Math.min(foothold.getX1(), foothold.getX2());
        int maxX = Math.max(foothold.getX1(), foothold.getX2());
        if (xAtCeiling < minX || xAtCeiling > maxX) {
            return AirCollision.none();
        }
        return new AirCollision(AirCollisionType.CEILING, new Point((int) Math.round(xAtCeiling), ceilingY + 1), foothold, progress);
    }

    private static boolean isWalkableGroundWallEndpoint(double yAtWall, int minY, int maxY) {
        if (Math.abs(yAtWall - minY) < 0.001d) {
            return true;
        }
        return Math.abs(yAtWall - ((double) maxY)) < 0.001d && maxY - minY <= cfg.MAX_SLOPE_UP;
    }

    private static double landingGroundHSpeed(MapleMap map, Foothold foothold, double incomingDeltaX, double incomingDeltaY, BotMovementProfile profile) {
        double landingDeltaX = incomingDeltaX;
        if (foothold != null && !foothold.isWall() && foothold.slope() != 0.0d) {
            double tangentX = foothold.getX2() - foothold.getX1();
            double tangentY = foothold.getY2() - foothold.getY1();
            double tangentLength = Math.hypot(tangentX, tangentY);
            if (tangentLength > 0.0d) {
                double unitX = tangentX / tangentLength;
                double unitY = tangentY / tangentLength;
                double dot = (incomingDeltaX * unitX) + (incomingDeltaY * unitY);
                landingDeltaX = unitX * dot;
            }
        }
        double landingDeltaX2 = landingDeltaX * 0.5d;
        double maxDeltaPerTick = Math.max(1.0d, walkStep(map, profile));
        return groundHSpeedFromTickDelta(map, Math.clamp(landingDeltaX2, -maxDeltaPerTick, maxDeltaPerTick), profile);
    }

    private static double groundHSpeedFromTickDelta(MapleMap map, double deltaXPerTick, BotMovementProfile profile) {
        double stepsPerTick = Math.max(1.0d, cfg.TICK_MS / CLIENT_GROUND_STEP_MS);
        return Math.clamp(deltaXPerTick / stepsPerTick, -maxHSpeedPerClientStep(profile), maxHSpeedPerClientStep(profile));
    }

    private static double tickDeltaFromGroundHSpeed(MapleMap map, double groundHSpeed, BotMovementProfile profile) {
        double stepsPerTick = Math.max(1.0d, cfg.TICK_MS / CLIENT_GROUND_STEP_MS);
        double clampedHSpeed = Math.clamp(groundHSpeed, -maxHSpeedPerClientStep(profile), maxHSpeedPerClientStep(profile));
        return clampedHSpeed * stepsPerTick;
    }

    private static RopeGrabResult simulateRopeGrabCore(MapleMap map, Point from, float initialVelY, int stepX, Rope targetRope, long landingGraceMs) {
        int i;
        if (targetRope == null) {
            return null;
        }
        float velocityY = initialVelY;
        double physX = from.x;
        double physY = from.y;
        int previousIntY = from.y;
        long remainingLandingGraceMs = Math.max(0L, landingGraceMs);
        float gravity = gravityPerTick();
        float maxFall = maxFallPerTick();
        int floorY = mapFloorY(map);
        for (int tick = 0; tick < FALL_SIM_TICK_CAP; tick++) {
            Point current = new Point((int) Math.round(physX), (int) Math.round(physY));
            if (canGrabRopeAtPoint(current, targetRope)) {
                return new RopeGrabResult(new Point(targetRope.x(), current.y), tick);
            }
            if (remainingLandingGraceMs > 0) {
                remainingLandingGraceMs = Math.max(0L, remainingLandingGraceMs - cfg.TICK_MS);
            }
            physX += stepX;
            physY += velocityY + (0.5f * gravity);
            velocityY = Math.min(velocityY + gravity, maxFall);
            int x = (int) Math.round(physX);
            int intY = (int) Math.round(physY);
            AirCollision collision = resolveAirCollision(map, new Point((int) Math.round(physX - stepX), previousIntY), new Point(x, intY));
            if (collision.type() == AirCollisionType.WALL) {
                physX = collision.point().x;
                physY = collision.point().y;
                stepX = 0;
                i = collision.point().y;
            } else if (collision.type() == AirCollisionType.CEILING) {
                physX = collision.point().x;
                physY = collision.point().y;
                velocityY = 0.0f;
                i = collision.point().y;
            } else {
                if ((collision.type() == AirCollisionType.LAND && (remainingLandingGraceMs == 0 || forbidFallDownLanding(collision))) || intY > floorY) {
                    return null;
                }
                i = intY;
            }
            previousIntY = i;
        }
        return null;
    }

    private static Point simulateRopeGrab(MapleMap map, Point from, float initialVelY, int stepX, Rope targetRope, long landingGraceMs) {
        RopeGrabResult result = simulateRopeGrabCore(map, from, initialVelY, stepX, targetRope, landingGraceMs);
        if (result != null) {
            return result.point();
        }
        return null;
    }

    private static int estimateRopeGrabTimeMs(MapleMap map, Point from, float initialVelY, int stepX, Rope targetRope, long landingGraceMs) {
        RopeGrabResult result = simulateRopeGrabCore(map, from, initialVelY, stepX, targetRope, landingGraceMs);
        if (result != null) {
            return result.ticks() * cfg.TICK_MS;
        }
        return Integer.MAX_VALUE;
    }

    private static boolean canGrabRopeAtPoint(Point position, Rope rope) {
        return Math.abs(position.x - rope.x()) <= cfg.ROPE_GRAB_X && position.y >= firstClimbableY(rope) && position.y <= rope.bottomY();
    }

    private static JumpLanding simulateLanding(MapleMap map, Point from, float initialVelY, int stepX, long landingGraceMs) {
        int i;
        float velocityY = initialVelY;
        double physX = from.x;
        double physY = from.y;
        int previousIntY = from.y;
        long remainingLandingGraceMs = Math.max(0L, landingGraceMs);
        float gravity = gravityPerTick();
        float maxFall = maxFallPerTick();
        int floorY = mapFloorY(map);
        for (int tick = 0; tick < FALL_SIM_TICK_CAP; tick++) {
            if (remainingLandingGraceMs > 0) {
                remainingLandingGraceMs = Math.max(0L, remainingLandingGraceMs - cfg.TICK_MS);
            }
            physX += stepX;
            physY += velocityY + (0.5f * gravity);
            velocityY = Math.min(velocityY + gravity, maxFall);
            int x = (int) Math.round(physX);
            int intY = (int) Math.round(physY);
            Point previousPoint = new Point((int) Math.round(physX - stepX), previousIntY);
            Point nextPoint = new Point(x, intY);
            AirCollision collision = resolveAirCollision(map, previousPoint, nextPoint);
            if (collision.type() == AirCollisionType.WALL) {
                physX = collision.point().x;
                physY = collision.point().y;
                stepX = 0;
                i = collision.point().y;
            } else if (collision.type() == AirCollisionType.CEILING) {
                physX = collision.point().x;
                physY = collision.point().y;
                velocityY = 0.0f;
                i = collision.point().y;
            } else {
                if (collision.type() == AirCollisionType.LAND && (remainingLandingGraceMs == 0 || forbidFallDownLanding(collision))) {
                    return new JumpLanding(collision.point(), collision.foothold(), nextPoint.x - previousPoint.x, nextPoint.y - previousPoint.y, tick + 1);
                }
                if (intY > floorY) {
                    return null;
                }
                i = intY;
            }
            previousIntY = i;
        }
        return null;
    }

    private static int estimateLandingTimeMs(MapleMap map, Point from, float initialVelY, int stepX, long landingGraceMs) {
        JumpLanding landing = simulateLanding(map, from, initialVelY, stepX, landingGraceMs);
        if (landing != null) {
            return landing.timeMs();
        }
        return Integer.MAX_VALUE;
    }
}
