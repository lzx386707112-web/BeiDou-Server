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
function enter(pi) {
    var mapId = pi.getPlayer().getMapId();
    if (mapId == 240060000) {
        return warpIfHeadDefeated(pi, 1, 240060100);
    } else if (mapId == 240060100) {
        return warpIfHeadDefeated(pi, 2, 240060200);
    }
    return false;
}

function warpIfHeadDefeated(pi, defeatedHeadCount, targetMap) {
    if (pi.getEventInstance().getIntProperty("defeatedHead") >= defeatedHeadCount) {
        pi.playPortalSound();
        pi.warp(targetMap, 0);
        return true;
    }

    pi.getPlayer().dropMessage(6, "Horntail's Seal is Blocking this Door.");
    return false;
}
