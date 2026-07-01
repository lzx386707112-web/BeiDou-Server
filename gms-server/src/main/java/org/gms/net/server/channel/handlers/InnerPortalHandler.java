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

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.net.AbstractPacketHandler;
import org.gms.net.packet.InPacket;
import org.gms.server.maps.MapleMap;
import org.gms.server.maps.Portal;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.Point;

/**
 * @author BubblesDev
 */
public final class InnerPortalHandler extends AbstractPacketHandler {
    private static final Logger log = LoggerFactory.getLogger(InnerPortalHandler.class);
    // 玩家需要处在内传送门附近，才认为这是一次有效“树洞/内传送”触发
    private static final double INNER_PORTAL_TRIGGER_DISTANCE_SQ = 90000.0; // 约 300 像素

    @Override
    public final void handlePacket(InPacket p, Client c) {
        Character player = c.getPlayer();
        if (!isPlayerReady(player) || p.available() <= 0) {
            log.info("[PortalTrace] USE_INNER_PORTAL reject-not-ready chr={} available={}",
                    player == null ? null : player.getName(), p.available());
            return;
        }

        String portalName = readPortalNameSafely(p);
        if (portalName == null || portalName.isEmpty()) {
            log.info("[PortalTrace] USE_INNER_PORTAL reject-empty-name chr={} map={} playerPos={}",
                    player.getName(), player.getMapId(), player.getPosition());
            return;
        }

        Portal sourcePortal = resolveValidSourcePortal(player, portalName);
        if (sourcePortal == null) {
            log.info("[PortalTrace] USE_INNER_PORTAL reject-source chr={} map={} packetPortal={} playerPos={}",
                    player.getName(), player.getMapId(), portalName, player.getPosition());
            return;
        }

        Point playerPos = player.getPosition();
        if (!isPlayerNearPortal(playerPos, sourcePortal)) {
            log.info("[PortalTrace] USE_INNER_PORTAL reject-distance chr={} map={} packetPortal={} playerPos={} portal={} distanceSq={}",
                    player.getName(), player.getMapId(), portalName, playerPos, describePortal(sourcePortal),
                    sourcePortal.getPosition().distanceSq(playerPos));
            return;
        }

        // 内传送仅处理“同图传送”；跨图传送交给常规换图流程，不记录本地传送上下文
        if (!isSameMapInnerTeleport(player, sourcePortal)) {
            log.info("[PortalTrace] USE_INNER_PORTAL ignore-cross-map chr={} map={} packetPortal={} portal={}",
                    player.getName(), player.getMapId(), portalName, describePortal(sourcePortal));
            return;
        }

        Portal targetPortal = resolveValidTargetPortal(player, sourcePortal);
        if (targetPortal == null) {
            log.info("[PortalTrace] USE_INNER_PORTAL reject-target chr={} map={} packetPortal={} portal={}",
                    player.getName(), player.getMapId(), portalName, describePortal(sourcePortal));
            return;
        }

        // 立即同步服务端坐标与可见对象状态，避免传送后首个攻击包仍使用旧坐标参与距离检测
        Point beforePos = new Point(playerPos);
        Point afterPos = new Point(targetPortal.getPosition());
        log.info("[PortalTrace] USE_INNER_PORTAL move chr={} map={} source={} target={} before={} after={}",
                player.getName(), player.getMapId(), describePortal(sourcePortal), describePortal(targetPortal), beforePos, afterPos);
        movePlayerInMap(player, afterPos);
        player.markTeleportLikeMove(beforePos, afterPos);
    }

    private static boolean isPlayerReady(Character player) {
        return player != null && player.getMap() != null;
    }

    private static String readPortalNameSafely(InPacket p) {
        // 协议通常会携带“当前触发的内传送门名”
        try {
            return p.readString();
        } catch (Exception ignored) {
            return null;
        }
    }

    private static Portal resolveValidSourcePortal(Character player, String portalName) {
        Portal sourcePortal = player.getMap().getPortal(portalName);
        if (sourcePortal == null || sourcePortal.getType() != Portal.TELEPORT_PORTAL) {
            return null;
        }
        return sourcePortal;
    }

    private static boolean isPlayerNearPortal(Point playerPos, Portal portal) {
        return playerPos != null && portal.getPosition().distanceSq(playerPos) <= INNER_PORTAL_TRIGGER_DISTANCE_SQ;
    }

    private static boolean isSameMapInnerTeleport(Character player, Portal sourcePortal) {
        return sourcePortal.getTargetMapId() == player.getMapId();
    }

    private static Portal resolveValidTargetPortal(Character player, Portal sourcePortal) {
        Portal targetPortal = player.getMap().getPortal(sourcePortal.getTarget());
        if (targetPortal == null || targetPortal.getPosition() == null) {
            return null;
        }
        return targetPortal;
    }

    private static void movePlayerInMap(Character player, Point afterPos) {
        MapleMap map = player.getMap();
        map.movePlayer(player, afterPos);
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
