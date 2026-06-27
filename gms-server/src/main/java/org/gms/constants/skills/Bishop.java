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
package org.gms.constants.skills;

/**
 * @author BubblesDev
 */
public class Bishop {
    public static final int MAPLE_WARRIOR = 2321000;
    public static final int BIG_BANG = 2321001;
    public static final int MANA_REFLECTION = 2321002;
    public static final int BAHAMUT = 2321003;
    public static final int INFINITY = 2321004;
    public static final int HOLY_SHIELD = 2321005;
    public static final int RESURRECTION = 2321006;
    public static final int ANGEL_RAY = 2321007;
    public static final int GENESIS = 2321008;
    public static final int HEROS_WILL = 2321009;
    public static final int DRAGON_2217_SWIFT = 2321010;
    public static final int DRAGON_2217_DIVE = 2321011;
    public static final int DRAGON_2217_BREATH = 2321012;
    public static final int DRAGON_2218_THUNDER_SWIFT = 2321013;
    public static final int DRAGON_2218_EARTH_DIVE = 2321014;
    public static final int DRAGON_2218_WIND_BREATH = 2321015;
    public static final int DRAGON_2220_SWIFT = 2321016;
    public static final int DRAGON_2220_DIVE = 2321017;
    public static final int DRAGON_2220_BREATH = 2321018;
    public static final int DRAGON_5TH_SWIFT = 2331010;
    public static final int DRAGON_5TH_DIVE = 2331011;
    public static final int DRAGON_5TH_BREATH = 2331012;
    public static final int DRAGON_5TH_THUNDER_SWIFT = 2331013;
    public static final int DRAGON_5TH_EARTH_DIVE = 2331014;
    public static final int DRAGON_5TH_WIND_BREATH = 2331015;
    public static final int DRAGON_5TH_6TH_SWIFT = 2331016;
    public static final int DRAGON_5TH_6TH_DIVE = 2331017;
    public static final int DRAGON_5TH_6TH_BREATH = 2331018;
    public static final int NEW_SKILL_TEST = DRAGON_2217_SWIFT;

    public static boolean isDragonCopySkill(int skill) {
        return skill == DRAGON_2217_SWIFT || skill == DRAGON_5TH_SWIFT;
    }

    public static boolean isDragonManualAttackSkill(int skill) {
        return (skill >= DRAGON_2217_DIVE && skill <= DRAGON_2220_BREATH)
                || (skill >= DRAGON_5TH_DIVE && skill <= DRAGON_5TH_6TH_BREATH);
    }
}
