/*
	This file is part of the OdinMS Maple Story Server
    Copyright (C) 2008 Patrick Huy <patrick.huy@frz.cc>
		       Matthias Butz <matze@odinms.de>
		       Jan Christian Meyer <vimes@odinms.de>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation version 3 as published by
    the Free Software Foundation. You may not use, modify or distribute
    this program under any other version of the GNU Affero General Public
    License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/
package org.gms.net.server.channel.handlers;

import org.gms.client.Client;
import org.gms.net.AbstractPacketHandler;
import org.gms.net.packet.InPacket;
import org.gms.server.Trade;
import org.gms.server.Trade.TradeResult;
import org.gms.server.maps.Portal;
import org.gms.util.PacketCreator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 传送点脚本传送玩家到指定地图触发
 */
public final class ChangeMapSpecialHandler extends AbstractPacketHandler {
    private static final Logger log = LoggerFactory.getLogger(ChangeMapSpecialHandler.class);

    @Override
    public final void handlePacket(InPacket p, Client c) {
        p.readByte();
        String startwp = p.readString();
        p.readShort();
        Portal portal = c.getPlayer().getMap().getPortal(startwp);
        logPortalTrace(c, startwp, portal, "received");
        if (portal == null) {
            logPortalTrace(c, startwp, null, "missing-portal");
            c.sendPacket(PacketCreator.enableActions());
            return;
        }
        if (c.getPlayer().portalDelay() > currentServerTime()) {
            logPortalTrace(c, startwp, portal, "reject-delay");
            c.sendPacket(PacketCreator.enableActions());
            return;
        }
        if (c.getPlayer().getBlockedPortals().contains(portal.getScriptName())) {
            logPortalTrace(c, startwp, portal, "reject-blocked-script");
            c.sendPacket(PacketCreator.enableActions());
            return;
        }
        if (c.getPlayer().isChangingMaps() || c.getPlayer().isBanned()) {
            logPortalTrace(c, startwp, portal, "reject-changing-or-banned");
            c.sendPacket(PacketCreator.enableActions());
            return;
        }
        if (c.getPlayer().getTrade() != null) {
            Trade.cancelTrade(c.getPlayer(), TradeResult.UNSUCCESSFUL_ANOTHER_MAP);
        }
        logPortalTrace(c, startwp, portal, "enter");
        portal.enterPortal(c);
    }

    private static void logPortalTrace(Client c, String packetPortalName, Portal portal, String stage) {
        org.gms.client.Character chr = c.getPlayer();
        log.info("[PortalTrace] CHANGE_MAP_SPECIAL {} chr={} map={} packetPortal={} playerPos={} portal={}",
                stage, chr.getName(), chr.getMapId(), packetPortalName, chr.getPosition(), describePortal(portal));
    }

    private static String describePortal(Portal portal) {
        if (portal == null) {
            return "null";
        }
        return String.format("id=%d name=%s type=%d tm=%d tn=%s script=%s pos=%s status=%s state=%s",
                portal.getId(),
                portal.getName(),
                portal.getType(),
                portal.getTargetMapId(),
                portal.getTarget(),
                portal.getScriptName(),
                portal.getPosition(),
                portal.getPortalStatus(),
                portal.getPortalState());
    }
}
