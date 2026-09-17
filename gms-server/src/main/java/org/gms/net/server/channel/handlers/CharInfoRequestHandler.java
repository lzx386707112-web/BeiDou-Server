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
import org.gms.server.maps.MapObject;
import org.gms.util.PacketCreator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import soloMapling.ArtificialPlayer.BotHelpers;

public final class CharInfoRequestHandler extends AbstractPacketHandler {
    private static final Logger log = LoggerFactory.getLogger(CharInfoRequestHandler.class);

    @Override
    public final void handlePacket(InPacket p, Client c) {
        p.skip(4);
        int cid = p.readInt();
        Character viewer = c.getPlayer();
        if (viewer == null || viewer.getMap() == null) {
            return;
        }
        Character player = viewer.getMap().getCharacterById(cid);
        if (player == null) {
            MapObject target = viewer.getMap().getMapObject(cid);
            if (target instanceof Character found) {
                player = found;
            }
        }
        if (player == null) {
            return;
        }
        try {
            if (viewer.getId() != player.getId()) {
                player.exportExcludedItems(c);
            }
            c.sendPacket(PacketCreator.charInfo(player));
        } catch (Exception e) {
            log.warn("Failed to send char info for {} (bot={})", player.getName(), BotHelpers.isBot(player), e);
        }
    }
}
