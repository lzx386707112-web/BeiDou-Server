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
public class BlazeWizard {
    // 1st job
    public static final int INCREASING_MAX_MP = 12000000;
    public static final int MAGIC_GUARD = 12001001;
    public static final int MAGIC_ARMOR = 12001002;
    public static final int MAGIC_CLAW = 12001003;
    public static final int FLAME = 12001004;
    // 2nd job
    public static final int MEDITATION = 12101000;
    public static final int SLOW = 12101001;
    public static final int FIRE_ARROW = 12101002;
    public static final int TELEPORT = 12101003;
    public static final int SPELL_BOOSTER = 12101004;
    public static final int ELEMENTAL_RESET = 12101005;
    public static final int FIRE_PILLAR = 12101006;
    // 3rd job
    public static final int ELEMENTAL_RESISTANCE = 12110000;
    public static final int ELEMENT_AMPLIFICATION = 12110001;
    public static final int SEAL = 12111002;
    public static final int METEOR_SHOWER = 12111003;
    public static final int IFRIT = 12111004;
    public static final int FLAME_GEAR = 12111005;
    public static final int FIRE_STRIKE = 12111006;

    // Custom 4th-job compatibility IDs for every TMS Blaze Wizard V/VI attack/state node.
    public static final int FLAME_DISCHARGE_LION = 12121001;
    public static final int FLAME_DISCHARGE_LION_BURST = 12121002;
    public static final int FLAME_DISCHARGE_LION_EMBER = 12121003;
    public static final int FLAME_DISCHARGE_LION_FINISH = 12121004;
    public static final int INFERNO_SPHERE = 12121007;
    public static final int MAGIC_ERUPTION_VI = 12121020;
    public static final int MAGIC_ERUPTION_VI_BREATH = 12121021;
    public static final int PHOENIX_DRIVE_VI = 12121022;
    public static final int ETERNAL_PHOENIX = 12121025;
    public static final int ETERNAL_PHOENIX_CYCLE = 12121026;
    public static final int ETERNAL_PHOENIX_STATE = 12121027;
    public static final int FLAME_CONCERTO = 12121028;
    public static final int FLAME_CONCERTO_FINISH = 12121029;
    public static final int INFERNO_SPHERE_TICK = 12121030;
    public static final int PHOENIX_DRIVE_VI_TICK = 12121033;
    public static final int ETERNAL_PHOENIX_BURST = 12121035;
    public static final int FLAME_CONCERTO_MAIN = 12121036;

    public static final int[] V_VI_ACTIVE_ATTACKS = {
        FLAME_DISCHARGE_LION,
        INFERNO_SPHERE,
        PHOENIX_DRIVE_VI,
        ETERNAL_PHOENIX,
        FLAME_CONCERTO
    };
}
