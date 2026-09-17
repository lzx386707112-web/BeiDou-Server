package soloMapling.ArtificialPlayer.BotTravelSystem;

import org.gms.server.maps.MapleMap;

import java.awt.Point;

public final class BotScriptedWarp {
    private BotScriptedWarp() {
    }

    public record WarpEdge(int fromMapId, int toMapId, String portalName, int toPortalId) {
        public WarpEdge(int fromMapId, int toMapId, String portalName) {
            this(fromMapId, toMapId, portalName, 0);
        }
    }

    public static int[] destinations(int mapId) {
        return new int[0];
    }

    public static WarpEdge edge(int fromMapId, int toMapId) {
        return null;
    }

    public static Point portalPos(MapleMap map, String portalName) {
        return null;
    }
}
