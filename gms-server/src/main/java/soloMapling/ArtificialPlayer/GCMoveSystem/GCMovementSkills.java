package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import org.gms.client.Character;
import org.gms.server.maps.Foothold;
import org.gms.server.maps.MapleMap;
import soloMapling.ArtificialPlayer.GCMoveSystem.GCMovement;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCMovementSkills.class */
final class GCMovementSkills {
    static final int TELEPORT_RANGE_PX = 150;
    static final int TELEPORT_Y_SNAP_PX = 75;
    static final int FLASH_JUMP_Y_SNAP_PX = 90;
    static final float[] FJ_SCALES = {1.0f, 0.75f, 0.55f};
    static final int[] FJ_TRAVEL_PX = {340, 240, 160};
    private static final int FJ_LAND_MARGIN_PX = 40;
    private static final int MOVE_DURATION_MS = 50;
    private static final byte CMD_ABSOLUTE = 0;
    private static final byte CMD_TELEPORT_DISAPPEAR = 3;
    private static final byte CMD_TELEPORT_APPEAR = 4;

    private GCMovementSkills() {
    }

    static boolean execTeleport(BotMovementState st, Character bot, int targetX, int targetY) {
        Point origin;
        Point dest;
        MapleMap map = bot.getMap();
        if (map == null || (origin = bot.getPosition()) == null) {
            return false;
        }
        int dx = targetX - origin.x;
        int dy = targetY - origin.y;
        if (Math.abs(dx) >= Math.abs(dy)) {
            dest = horizontalLanding(map, origin, dx >= 0 ? 1 : -1, TELEPORT_RANGE_PX, TELEPORT_Y_SNAP_PX);
        } else if (dy > 0) {
            dest = downLanding(map, origin);
        } else {
            dest = upLanding(map, origin);
        }
        if (dest == null) {
            return false;
        }
        if (dest.x == origin.x && dest.y == origin.y) {
            return false;
        }
        int hdir = dest.x >= origin.x ? 1 : -1;
        boolean downward = dest.y > origin.y + 8;
        int stance = downward ? proneStance(hdir) : standStance(hdir);
        BotPhysicsEngine.teleportTo(st, bot, dest);
        BotMovementManager.resetEntryStateAfterTeleport(st);
        if (ObserverTracker.isActiveMap(bot.getMapId())) {
            broadcastTeleport(bot, origin, dest, stance);
            return true;
        }
        return true;
    }

    static boolean execFlashJump(BotMovementState st, Character bot, int targetX, float scaleCap) {
        Point origin;
        MapleMap map = bot.getMap();
        if (map == null || (origin = bot.getPosition()) == null || st.inAir || st.climbing) {
            return false;
        }
        int dir = targetX >= origin.x ? 1 : -1;
        float scale = fitScale(map, origin, dir, scaleCap);
        if (scale <= 0.0f) {
            return false;
        }
        BotMovementManager.initiateJump(st, bot, targetX - origin.x);
        st.flashJumpScale = scale;
        st.pendingFlashJump = true;
        return true;
    }

    static boolean execFlashJumpForced(BotMovementState st, Character bot, int dir, float scale) {
        Point origin = bot.getPosition();
        if (bot.getMap() == null || origin == null || st.inAir || st.climbing) {
            return false;
        }
        BotMovementManager.initiateJump(st, bot, dir >= 0 ? 1 : -1);
        st.flashJumpScale = Math.max(0.2f, Math.min(scale, 1.0f));
        st.pendingFlashJump = true;
        return true;
    }

    private static float fitScale(MapleMap map, Point origin, int dir, float cap) {
        int run = sameLedgeRun(map, origin, dir);
        for (int i = 0; i < FJ_SCALES.length; i++) {
            if (FJ_SCALES[i] <= cap + 0.001f) {
                int travel = FJ_TRAVEL_PX[i];
                if (run >= 0) {
                    if (run - FJ_LAND_MARGIN_PX >= travel) {
                        return FJ_SCALES[i];
                    }
                } else if (landingProbe(map, origin, dir, travel) != null) {
                    return FJ_SCALES[i];
                }
            }
        }
        return 0.0f;
    }

    private static int sameLedgeRun(MapleMap map, Point origin, int dir) {
        int region = GCMovement.regionIdAt(map, origin.x, origin.y);
        if (region < 0) {
            return -1;
        }
        for (GCMovement.Ledge l : GCMovement.walkableLedges(map)) {
            if (l.regionId() == region) {
                return dir > 0 ? l.maxX() - origin.x : origin.x - l.minX();
            }
        }
        return -1;
    }

    private static Point landingProbe(MapleMap map, Point origin, int dir, int travel) {
        for (int reach = travel; reach >= travel - 60; reach -= 20) {
            Point g = GCMovement.groundPointBelow(map, origin.x + (dir * reach), origin.y - 4);
            if (g != null && Math.abs(g.y - origin.y) <= FLASH_JUMP_Y_SNAP_PX) {
                return g;
            }
        }
        return null;
    }

    private static Point horizontalLanding(MapleMap map, Point origin, int dir, int range, int ySnap) {
        for (int reach = range; reach >= FJ_LAND_MARGIN_PX; reach -= 25) {
            int tx = origin.x + (dir * reach);
            Point g = GCMovement.groundPointBelow(map, tx, origin.y - 4);
            if (g != null && Math.abs(g.y - origin.y) <= ySnap) {
                return g;
            }
        }
        return null;
    }

    private static Point upLanding(MapleMap map, Point origin) {
        return BotPhysicsEngine.findGroundPointAbove(map, origin, TELEPORT_RANGE_PX);
    }

    private static Point downLanding(MapleMap map, Point origin) {
        Point best = null;
        Point probe = GCMovement.groundPointBelow(map, origin.x, origin.y + 1);
        int guard = 0;
        while (probe != null && probe.y > origin.y && probe.y - origin.y <= TELEPORT_RANGE_PX) {
            int i = guard;
            guard++;
            if (i >= 12) {
                break;
            }
            best = probe;
            probe = GCMovement.groundPointBelow(map, origin.x, probe.y + 1);
        }
        return best;
    }

    private static void broadcastTeleport(Character bot, Point origin, Point dest, int stance) {
        MapleMap map = bot.getMap();
        byte[] data = new byte[35];
        int i = 0 + 1;
        data[0] = CMD_TELEPORT_DISAPPEAR;
        putAbsoluteFrag(data, putTeleportFrag(data, putTeleportFrag(data, i, (byte) 4, origin.x, origin.y, footholdIdAt(map, origin), stance), (byte) 3, dest.x, dest.y, 0, stance), dest.x, dest.y, 0, 0, footholdIdAt(map, dest), stance, MOVE_DURATION_MS);
        BotMovementManager.broadcastRawMovement(bot, data);
    }

    private static int putAbsoluteFrag(byte[] d, int i, int x, int y, int velX, int velY, int fh, int stance, int durMs) {
        d[i] = 0;
        int i2 = putShort(d, putShort(d, putShort(d, putShort(d, putShort(d, i + 1, x), y), velX), velY), fh);
        d[i2] = (byte) stance;
        return putShort(d, i2 + 1, durMs);
    }

    private static int putTeleportFrag(byte[] d, int i, byte cmd, int x, int y, int fh, int stance) {
        d[i] = cmd;
        int i2 = putShort(d, putShort(d, putShort(d, i + 1, x), y), fh);
        d[i2] = (byte) stance;
        return putShort(d, i2 + 1, 0);
    }

    private static int putShort(byte[] d, int i, int v) {
        d[i] = (byte) (v & 255);
        d[i + 1] = (byte) ((v >> 8) & 255);
        return i + 2;
    }

    private static int footholdIdAt(MapleMap map, Point p) {
        Foothold fh = BotPhysicsEngine.findGroundFoothold(map, p);
        if (fh != null) {
            return fh.getId();
        }
        return 0;
    }

    private static int standStance(int dir) {
        return dir < 0 ? 5 : 4;
    }

    private static int proneStance(int dir) {
        return dir < 0 ? 11 : 10;
    }
}
