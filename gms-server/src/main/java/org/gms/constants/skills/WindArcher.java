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
public class WindArcher {
    // 1st job
    public static final int CRITICAL_SHOT = 13000000;
    public static final int EYE_OF_AMAZON = 13000001;
    public static final int FOCUS = 13001002;
    public static final int DOUBLE_SHOT = 13001003;
    public static final int STORM = 13001004;
    // 2nd job
    public static final int BOW_MASTERY = 13100000;
    public static final int BOW_BOOSTER = 13101001;
    public static final int FINAL_ATTACK = 13101002;
    public static final int SOUL_ARROW = 13101003;
    public static final int THRUST = 13100004;
    public static final int STORM_BREAK = 13101005;
    public static final int WIND_WALK = 13101006;
    // 3rd job
    public static final int ARROW_RAIN = 13111000;
    public static final int HURRICANE = 13111002;
    public static final int BOW_EXPERT = 13110003;
    public static final int PUPPET = 13111004;
    public static final int EAGLE_EYE = 13111005;
    public static final int WIND_PIERCING = 13111006;
    public static final int WIND_SHOT = 13111007;
    public static final int STRAFE = 13111001;

    // TMS V/VI compatibility IDs in the otherwise empty 1312 skill book.
    public static final int MERCILESS_WINDS = 13121003;
    public static final int GALE_BARRIER = 13121004;
    public static final int GALE_BARRIER_TORNADO = 13121005;
    public static final int FAIRY_SPIRAL_VI = 13121009;
    public static final int MONSOON_VI = 13121010;
    public static final int ANEMOI = 13121011;
    public static final int ANEMOI_GALE = 13121012;
    public static final int MISTRAL_SPRING = 13121013;
    public static final int MISTRAL_WIND_BLADE = 13121014;
    public static final int MISTRAL_SPIRIT = 13121015;
    public static final int MISTRAL_HAPPY_SPIRIT = 13121016;
    public static final int MISTRAL_FIERCE_SPIRIT = 13121017;
    public static final int MERCILESS_WINDS_SPIRIT = 13121018;
    public static final int ELEMENTAL_TEMPEST = 13121019;
    public static final int ELEMENTAL_TEMPEST_ARROW_RAIN = 13121020;
    public static final int ELEMENTAL_TEMPEST_WAVE = 13121023;

    public static final int[] V_VI_ACTIVE_ATTACKS = {
        MERCILESS_WINDS,
        GALE_BARRIER,
        FAIRY_SPIRAL_VI,
        MONSOON_VI,
        ANEMOI,
        MISTRAL_SPRING,
        ELEMENTAL_TEMPEST
    };
}
