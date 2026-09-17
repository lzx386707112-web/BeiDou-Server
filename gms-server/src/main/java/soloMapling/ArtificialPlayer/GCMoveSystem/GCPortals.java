package soloMapling.ArtificialPlayer.GCMoveSystem;

import org.gms.client.Character;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Portal;

/* loaded from: asm-bot-mini.jar:org/gms/soloMapling/ArtificialPlayer/GCMoveSystem/GCPortals.class */
final class GCPortals {
    private GCPortals() {
    }

    static boolean enter(Character bot, Portal portal) {
        MapleMap mapInstance;
        if (bot == null || portal == null || bot.getMap() == null) {
            return false;
        }
        int targetMapId = portal.getTargetMapId();
        try {
            if (bot.getEventInstance() == null) {
                mapInstance = bot.getMap().getChannelServer().getMapFactory().getMap(targetMapId);
            } else {
                mapInstance = bot.getEventInstance().getMapInstance(targetMapId);
            }
            MapleMap to = mapInstance;
            if (to == null) {
                bot.changeMap(targetMapId);
                return true;
            }
            Portal pto = to.getPortal(portal.getTarget());
            if (pto == null) {
                pto = to.getPortal(0);
            }
            bot.changeMap(to, pto);
            return true;
        } catch (Exception e) {
            try {
                bot.changeMap(targetMapId);
                return true;
            } catch (Exception e2) {
                return false;
            }
        }
    }
}
