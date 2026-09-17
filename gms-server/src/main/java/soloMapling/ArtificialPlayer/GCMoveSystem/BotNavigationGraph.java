package soloMapling.ArtificialPlayer.GCMoveSystem;

import java.awt.Point;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.gms.server.maps.Foothold;
import org.gms.server.maps.MapleMap;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraph.class */
final class BotNavigationGraph implements Serializable {
    private static final long serialVersionUID = 1;
    final int mapId;
    final int version;
    final BotMovementProfile movementProfile;
    final List<Region> regions;
    final Map<Integer, Region> regionsById;
    final Map<Integer, Integer> regionIdByFootholdId;
    final Map<Integer, List<Edge>> outgoingByRegionId;
    final Set<Integer> collidableWallIds;
    final Set<Integer> collidableFromBelowIds;

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraph$EdgeType.class */
    enum EdgeType {
        WALK,
        JUMP,
        DROP,
        CLIMB,
        PORTAL
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraph$Segment.class */
    static final class Segment implements Serializable {
        private static final long serialVersionUID = 1;
        final int footholdId;
        final int x1;
        final int y1;
        final int x2;
        final int y2;
        final int minX;
        final int maxX;
        final boolean forbidFallDown;
        final boolean collidableFromBelow;

        Segment(Foothold foothold) {
            this(foothold, false);
        }

        Segment(Foothold foothold, boolean collidableFromBelow) {
            this.footholdId = foothold.getId();
            this.x1 = foothold.getX1();
            this.y1 = foothold.getY1();
            this.x2 = foothold.getX2();
            this.y2 = foothold.getY2();
            this.minX = Math.min(this.x1, this.x2);
            this.maxX = Math.max(this.x1, this.x2);
            this.forbidFallDown = foothold.isForbidFallDown();
            this.collidableFromBelow = collidableFromBelow;
        }

        boolean containsX(int x) {
            return x >= this.minX && x <= this.maxX;
        }

        int clampX(int x) {
            if (x < this.minX) {
                return this.minX;
            }
            if (x > this.maxX) {
                return this.maxX;
            }
            return x;
        }

        Point pointAt(int x) {
            int clampedX = clampX(x);
            if (this.x1 == this.x2) {
                return new Point(clampedX, Math.min(this.y1, this.y2));
            }
            double ratio = (clampedX - this.x1) / (this.x2 - this.x1);
            int y = (int) Math.round(this.y1 + ((this.y2 - this.y1) * ratio));
            return new Point(clampedX, y);
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraph$Region.class */
    static final class Region implements Serializable {
        private static final long serialVersionUID = 1;
        final int id;
        final List<Segment> segments;
        final int minX;
        final int maxX;
        final int minY;
        final int maxY;
        final boolean isRopeRegion;
        final boolean isLadder;

        Region(int id, List<Segment> segments) {
            if (segments.isEmpty()) {
                throw new IllegalArgumentException("Bot nav region requires at least one segment");
            }
            this.id = id;
            this.segments = new ArrayList(segments);
            this.isRopeRegion = false;
            this.isLadder = false;
            int regionMinX = Integer.MAX_VALUE;
            int regionMaxX = Integer.MIN_VALUE;
            int regionMinY = Integer.MAX_VALUE;
            int regionMaxY = Integer.MIN_VALUE;
            for (Segment segment : segments) {
                regionMinX = Math.min(regionMinX, segment.minX);
                regionMaxX = Math.max(regionMaxX, segment.maxX);
                regionMinY = Math.min(regionMinY, Math.min(segment.y1, segment.y2));
                regionMaxY = Math.max(regionMaxY, Math.max(segment.y1, segment.y2));
            }
            this.minX = regionMinX;
            this.maxX = regionMaxX;
            this.minY = regionMinY;
            this.maxY = regionMaxY;
        }

        Region(int id, int ropeX, int topY, int bottomY, boolean isLadder) {
            this.id = id;
            this.segments = List.of();
            this.isRopeRegion = true;
            this.isLadder = isLadder;
            this.minX = ropeX;
            this.maxX = ropeX;
            this.minY = topY;
            this.maxY = bottomY;
        }

        int width() {
            return Math.max(0, this.maxX - this.minX);
        }

        int height() {
            return Math.max(0, this.maxY - this.minY);
        }

        Point leftPoint() {
            return pointAt(this.minX);
        }

        Point centerPoint() {
            if (this.isRopeRegion) {
                return new Point(this.minX, this.minY + (height() / 2));
            }
            return pointAt(this.minX + (width() / 2));
        }

        Point rightPoint() {
            return pointAt(this.maxX);
        }

        Point pointAt(int x) {
            if (this.isRopeRegion) {
                return new Point(this.minX, this.minY + (height() / 2));
            }
            Segment bestSegment = findBestSegment(x);
            return bestSegment.pointAt(x);
        }

        boolean isForbidFallDownAt(int x) {
            if (this.isRopeRegion || this.segments.isEmpty()) {
                return false;
            }
            return findBestSegment(x).forbidFallDown;
        }

        private Segment findBestSegment(int x) {
            Segment best = this.segments.get(0);
            int bestDistance = distanceToSegment(best, x);
            for (int i = 1; i < this.segments.size(); i++) {
                Segment segment = this.segments.get(i);
                int distance = distanceToSegment(segment, x);
                if (distance < bestDistance) {
                    best = segment;
                    bestDistance = distance;
                }
            }
            return best;
        }

        private int distanceToSegment(Segment segment, int x) {
            if (segment.containsX(x)) {
                return 0;
            }
            return x < segment.minX ? segment.minX - x : x - segment.maxX;
        }
    }

    /* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/BotNavigationGraph$Edge.class */
    static final class Edge implements Serializable {
        private static final long serialVersionUID = 1;
        final int fromRegionId;
        final int toRegionId;
        final EdgeType type;
        final Point startPoint;
        final Point endPoint;
        final int launchMinX;
        final int launchMaxX;
        final int launchStepX;
        final int portalId;
        final int ropeX;
        final int ropeTopY;
        final int ropeBottomY;
        final int cost;

        Edge(int fromRegionId, int toRegionId, EdgeType type, Point startPoint, Point endPoint, int launchMinX, int launchMaxX, int launchStepX, int portalId, int ropeX, int ropeTopY, int ropeBottomY, int cost) {
            this.fromRegionId = fromRegionId;
            this.toRegionId = toRegionId;
            this.type = type;
            this.startPoint = new Point(startPoint);
            this.endPoint = new Point(endPoint);
            this.launchMinX = Math.min(launchMinX, launchMaxX);
            this.launchMaxX = Math.max(launchMinX, launchMaxX);
            this.launchStepX = launchStepX;
            this.portalId = portalId;
            this.ropeX = ropeX;
            this.ropeTopY = ropeTopY;
            this.ropeBottomY = ropeBottomY;
            this.cost = cost;
        }

        Edge(int fromRegionId, int toRegionId, EdgeType type, Point startPoint, Point endPoint, int launchStepX, int portalId, int ropeX, int ropeTopY, int ropeBottomY, int cost) {
            this(fromRegionId, toRegionId, type, startPoint, endPoint, startPoint.x, startPoint.x, launchStepX, portalId, ropeX, ropeTopY, ropeBottomY, cost);
        }

        boolean containsLaunchX(int x) {
            return x >= this.launchMinX && x <= this.launchMaxX;
        }

        boolean containsLaunchX(int x, int tolerance) {
            return x >= this.launchMinX - tolerance && x <= this.launchMaxX + tolerance;
        }

        Point pointAtNearestLaunchX(int x) {
            return new Point(Math.clamp(x, this.launchMinX, this.launchMaxX), this.startPoint.y);
        }
    }

    BotNavigationGraph(int mapId, int version, BotMovementProfile movementProfile, List<Region> regions, Map<Integer, Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, List<Edge>> outgoingByRegionId, Set<Integer> collidableWallIds) {
        this(mapId, version, movementProfile, regions, regionsById, regionIdByFootholdId, outgoingByRegionId, collidableWallIds, Set.of());
    }

    BotNavigationGraph(int mapId, int version, BotMovementProfile movementProfile, List<Region> regions, Map<Integer, Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, List<Edge>> outgoingByRegionId, Set<Integer> collidableWallIds, Set<Integer> collidableFromBelowIds) {
        this.mapId = mapId;
        this.version = version;
        this.movementProfile = movementProfile;
        this.regions = new ArrayList(regions);
        this.regionsById = new HashMap(regionsById);
        this.regionIdByFootholdId = new HashMap(regionIdByFootholdId);
        this.outgoingByRegionId = new HashMap();
        for (Map.Entry<Integer, List<Edge>> entry : outgoingByRegionId.entrySet()) {
            this.outgoingByRegionId.put(entry.getKey(), new ArrayList(entry.getValue()));
        }
        this.collidableWallIds = new HashSet(collidableWallIds);
        this.collidableFromBelowIds = new HashSet(collidableFromBelowIds);
    }

    BotNavigationGraph(int mapId, int version, List<Region> regions, Map<Integer, Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, List<Edge>> outgoingByRegionId, Set<Integer> collidableWallIds) {
        this(mapId, version, BotMovementProfile.base(), regions, regionsById, regionIdByFootholdId, outgoingByRegionId, collidableWallIds, Set.of());
    }

    BotNavigationGraph(int mapId, int version, List<Region> regions, Map<Integer, Region> regionsById, Map<Integer, Integer> regionIdByFootholdId, Map<Integer, List<Edge>> outgoingByRegionId, Set<Integer> collidableWallIds, Set<Integer> collidableFromBelowIds) {
        this(mapId, version, BotMovementProfile.base(), regions, regionsById, regionIdByFootholdId, outgoingByRegionId, collidableWallIds, collidableFromBelowIds);
    }

    Region getRegion(int regionId) {
        return this.regionsById.get(Integer.valueOf(regionId));
    }

    List<Edge> getOutgoing(int regionId) {
        return this.outgoingByRegionId.getOrDefault(Integer.valueOf(regionId), List.of());
    }

    boolean hasInterRegionEdge(int fromRegionId, int toRegionId) {
        for (Edge edge : getOutgoing(fromRegionId)) {
            if (edge.fromRegionId != edge.toRegionId && edge.toRegionId == toRegionId) {
                return true;
            }
        }
        return false;
    }

    Set<Integer> getMutualAdjacentRegionIds(int regionId) {
        Set<Integer> adjacent = new HashSet<>();
        for (Edge edge : getOutgoing(regionId)) {
            if (edge.fromRegionId != edge.toRegionId && hasInterRegionEdge(edge.toRegionId, regionId)) {
                adjacent.add(Integer.valueOf(edge.toRegionId));
            }
        }
        return adjacent;
    }

    int findRegionId(MapleMap map, Point position) {
        int regionId;
        if (position == null || map.getFootholds() == null) {
            return -1;
        }
        Foothold foothold = BotPhysicsEngine.findGroundFoothold(map, position);
        if (foothold != null && (regionId = this.regionIdByFootholdId.getOrDefault(Integer.valueOf(foothold.getId()), -1).intValue()) >= 0) {
            return regionId;
        }
        return findRopeRegionId(position);
    }

    int findRopeRegionId(Point position) {
        for (Region region : this.regions) {
            if (region.isRopeRegion && Math.abs(position.x - region.minX) <= BotPhysicsEngine.cfg.ROPE_GRAB_X && position.y >= region.minY && position.y <= region.maxY) {
                return region.id;
            }
        }
        return -1;
    }
}
