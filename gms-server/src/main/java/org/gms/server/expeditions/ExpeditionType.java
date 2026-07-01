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

package org.gms.server.expeditions;

import org.gms.config.GameConfig;

/**
 * @author Alan (SharpAceX)
 */

public enum ExpeditionType {
    BALROG_EASY(1, 30, 50, 255, 5),
    BALROG_NORMAL(1, 30, 50, 255, 5),
    SCARGA(1, 30, 100, 255, 5),
    SHOWA(1, 30, 100, 255, 5),
    ZAKUM(1, 30, 50, 255, 5),
    HORNTAIL(1, 30, 100, 255, 5),
    CHAOS_ZAKUM(1, 30, 120, 255, 5),
    CHAOS_HORNTAIL(1, 30, 120, 255, 5),
    ARIANT(1, 7, 20, 255, 5),
    ARIANT1(1, 7, 20, 255, 5),
    ARIANT2(1, 7, 20, 255, 5),
    PINKBEAN(1, 30, 120, 255, 5),
    CWKPQ(1, 30, 90, 255, 5),   // CWKPQ min-level 90, found thanks to Cato
    CYGNUS(1, 30, 170, 255, 5);

    private final int minSize;
    private final int maxSize;
    private final int minLevel;
    private final int maxLevel;
    private final int registrationMinutes;

    ExpeditionType(int minSize, int maxSize, int minLevel, int maxLevel, int minutes) {
        this.minSize = minSize;
        this.maxSize = maxSize;
        this.minLevel = minLevel;
        this.maxLevel = maxLevel;
        this.registrationMinutes = minutes;
    }

    public int getMinSize() {
        return !GameConfig.getServerBoolean("use_enable_solo_expeditions") ? minSize : 1;
    }

    public int getMaxSize() {
        return maxSize;
    }

    public int getMinLevel() {
        return minLevel;
    }

    public int getMaxLevel() {
        return maxLevel;
    }

    public int getRegistrationMinutes() {
        return registrationMinutes;
    }
}
