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
public class ThunderBreaker {
    // 1st job
    public static final int QUICK_MOTION = 15000000;
    public static final int FIRST_STRIKE = 15001001;
    public static final int SOMERSAULT_KICK = 15001002;
    public static final int DASH = 15001003;
    public static final int LIGHTNING = 15001004;
    // 2nd job
    public static final int IMPROVE_MAX_HP = 15100000;
    public static final int KNUCKLER_MASTERY = 15100001;
    public static final int KNUCKLER_BOOSTER = 15101002;
    public static final int CORKSCREW_BLOW = 15101003;
    public static final int ENERGY_CHARGE = 15100004;
    public static final int ENERGY_BLAST = 15101005;
    public static final int LIGHTNING_CHARGE = 15101006;
    // 3rd job
    public static final int CRITICAL_PUNCH = 15110000;
    public static final int TRANSFORMATION = 15111002;
    public static final int BARRAGE = 15111004;
    public static final int SPEED_INFUSION = 15111005;
    public static final int SHOCK_WAVE = 15111003;
    public static final int ENERGY_DRAIN = 15111001;
    public static final int SPARK = 15111006;
    public static final int SHARK_WAVE = 15111007;

    // Custom 4th-job compatibility IDs for TMS Thunder Breaker V/VI attacks.
    public static final int SEA_DRAGON_SPIRAL = 15121000;
    public static final int SHARK_TORPEDO = 15121001;
    public static final int LIGHTNING_SPEAR_MULTISTRIKE = 15121002;
    public static final int LIGHTNING_SPEAR_STRIKE_1 = 15121003;
    public static final int LIGHTNING_SPEAR_STRIKE_2 = 15121004;
    public static final int LIGHTNING_SPEAR_STRIKE_3 = 15121005;
    public static final int LIGHTNING_SPEAR_STRIKE_4 = 15121006;
    public static final int LIGHTNING_SPEAR_STRIKE_5 = 15121007;
    public static final int LIGHTNING_SPEAR_STRIKE_6 = 15121008;
    public static final int LIGHTNING_SPEAR_THUNDER = 15121009;
    public static final int LIGHTNING_SPEAR_FINISH = 15121010;
    public static final int LIGHTNING_SPEAR_GIANT_THUNDER = 15121011;
    public static final int ANNIHILATE_VI = 15121012;
    public static final int THUNDERBOLT_VI = 15121013;
    public static final int THUNDERBOLT_FLASH = 15121014;
    public static final int TYPHOON_VI = 15121015;
    public static final int GOD_OF_THE_SEA_VI = 15121016;
    public static final int WAVE_RIDING_THUNDER = 15121017;
    public static final int WAVE_RIDING_THUNDER_SHOCK = 15121018;
    public static final int SWIFT_ANNIHILATION = 15121019;
    public static final int SWIFT_ANNIHILATION_SURGE = 15121020;

    public static final int[] V_VI_ACTIVE_ATTACKS = {
        SEA_DRAGON_SPIRAL,
        SHARK_TORPEDO,
        LIGHTNING_SPEAR_MULTISTRIKE,
        ANNIHILATE_VI,
        THUNDERBOLT_VI,
        TYPHOON_VI,
        GOD_OF_THE_SEA_VI,
        WAVE_RIDING_THUNDER,
        SWIFT_ANNIHILATION
    };
}
