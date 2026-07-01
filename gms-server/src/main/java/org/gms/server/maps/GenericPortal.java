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
package org.gms.server.maps;

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.constants.game.GameConstants;
import org.gms.constants.id.MapId;
import org.gms.scripting.portal.PortalScriptManager;
import org.gms.util.PacketCreator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.awt.*;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class GenericPortal implements Portal {
    private static final Logger log = LoggerFactory.getLogger(GenericPortal.class);
    private String name;
    private String target;
    private Point position;
    private int targetmap;
    private final int type;
    private boolean status = true;
    private int id;
    private String scriptName;
    private boolean portalState;
    private Lock scriptLock = null;

    public GenericPortal(int type) {
        this.type = type;
    }

    @Override
    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    @Override
    public String getName() {
        return name;
    }

    @Override
    public Point getPosition() {
        return position;
    }

    @Override
    public String getTarget() {
        return target;
    }

    @Override
    public void setPortalStatus(boolean newStatus) {
        this.status = newStatus;
    }

    @Override
    public boolean getPortalStatus() {
        return status;
    }

    @Override
    public int getTargetMapId() {
        return targetmap;
    }

    @Override
    public int getType() {
        return type;
    }

    @Override
    public String getScriptName() {
        return scriptName;
    }

    public void setName(String name) {
        this.name = name;
    }

    public void setPosition(Point position) {
        this.position = position;
    }

    public void setTarget(String target) {
        this.target = target;
    }

    public void setTargetMapId(int targetmapid) {
        this.targetmap = targetmapid;
    }

    @Override
    public void setScriptName(String scriptName) {
        this.scriptName = scriptName;

        if (scriptName != null) {
            if (scriptLock == null) {
                scriptLock = new ReentrantLock(true);
            }
        } else {
            scriptLock = null;
        }
    }

    @Override
    public void enterPortal(Client c) {
        boolean changed = false;
        Character chr = c.getPlayer();
        log.info("[PortalTrace] ENTER start chr={} map={} portal={}", chr.getName(), chr.getMapId(), describeSelf());
        if (getScriptName() != null) {
            try {
                scriptLock.lock();
                try {
                    changed = PortalScriptManager.getInstance().executePortalScript(this, c);
                    log.info("[PortalTrace] ENTER script-result chr={} map={} portal={} changed={}",
                            chr.getName(), chr.getMapId(), describeSelf(), changed);
                } finally {
                    scriptLock.unlock();
                }
            } catch (NullPointerException npe) {
                log.error("[PortalTrace] ENTER script-null-error chr={} map={} portal={}", chr.getName(), chr.getMapId(), describeSelf(), npe);
                npe.printStackTrace();
            }
        } else if (getTargetMapId() != MapId.NONE) {
            if (!(chr.getChalkboard() != null && GameConstants.isFreeMarketRoom(getTargetMapId()))) {
                MapleMap to = chr.getEventInstance() == null ? c.getChannelServer().getMapFactory().getMap(getTargetMapId()) : chr.getEventInstance().getMapInstance(getTargetMapId());
                Portal pto = to.getPortal(getTarget());
                if (pto == null) {// fallback for missing portals - no real life case anymore - interesting for not implemented areas
                    log.info("[PortalTrace] ENTER target-portal-missing chr={} fromMap={} toMap={} targetName={} fallback=0 source={}",
                            chr.getName(), chr.getMapId(), getTargetMapId(), getTarget(), describeSelf());
                    pto = to.getPortal(0);
                }
                log.info("[PortalTrace] ENTER warp chr={} fromMap={} toMap={} targetPortal={}",
                        chr.getName(), chr.getMapId(), getTargetMapId(), describePortal(pto));
                chr.changeMap(to, pto); //late resolving makes this harder but prevents us from loading the whole world at once
                changed = true;
            } else {
                chr.dropMessage(5, "You cannot enter this map with the chalkboard opened.");
                log.info("[PortalTrace] ENTER reject-chalkboard chr={} map={} portal={}", chr.getName(), chr.getMapId(), describeSelf());
            }
        } else {
            log.info("[PortalTrace] ENTER no-target chr={} map={} portal={}", chr.getName(), chr.getMapId(), describeSelf());
        }
        if (!changed) {
            log.info("[PortalTrace] ENTER unchanged chr={} map={} portal={}", chr.getName(), chr.getMapId(), describeSelf());
            c.sendPacket(PacketCreator.enableActions());
        }
    }

    @Override
    public void setPortalState(boolean state) {
        this.portalState = state;
    }

    @Override
    public boolean getPortalState() {
        return portalState;
    }

    private String describeSelf() {
        return String.format("id=%d name=%s type=%d tm=%d tn=%s script=%s pos=%s status=%s state=%s",
                getId(), getName(), getType(), getTargetMapId(), getTarget(), getScriptName(), getPosition(), getPortalStatus(), getPortalState());
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
