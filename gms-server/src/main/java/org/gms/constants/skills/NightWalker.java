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
public class NightWalker {
    // 1st job
    public static final int NIMBLE_BODY = 14000000;
    public static final int KEEN_EYES = 14000001;
    public static final int DISORDER = 14000002;
    public static final int DARK_SIGHT = 14001003;
    public static final int LUCKY_SEVEN = 14001004;
    public static final int DARKNESS = 14001005;
    // 2nd job
    public static final int CLAW_MASTERY = 14100000;
    public static final int CRITICAL_THROW = 14100001;
    public static final int CLAW_BOOSTER = 14101002;
    public static final int HASTE = 14101003;
    public static final int FLASH_JUMP = 14101004;
    public static final int VANISH = 14100005;
    public static final int VAMPIRE = 14101006;
    // 3rd job
    public static final int SHADOW_PARTNER = 14111000;
    public static final int SHADOW_WEB = 14111001;
    public static final int AVENGER = 14111002;
    public static final int ALCHEMIST = 14110003;
    public static final int VENOM = 14110004;
    public static final int TRIPLE_THROW = 14110005;
    public static final int POISON_BOMB = 14111006;

    // TMS V/VI compatibility IDs in the otherwise empty 1412 skill book.
    public static final int SHADOW_BITE = 14121003;
    public static final int RAPID_THROW = 14121004;
    public static final int RAPID_THROW_FINISH = 14121005;
    public static final int RAPID_THROW_UPPER_DART = 14121006;
    public static final int RAPID_THROW_MIDDLE_DART = 14121007;
    public static final int RAPID_THROW_LOWER_DART = 14121008;
    public static final int SHADOW_BITE_NORMAL_HIT = 14121014;
    public static final int SHADOW_BITE_BOSS_HIT = 14121015;
    public static final int SHADOW_BITE_SHADOW_BAT = 14121016;
    public static final int SHADOW_BITE_RAVENOUS_BAT = 14121017;
    public static final int DOMINION_VI_TICK = 14121018;
    public static final int DARK_OMEN_VI = 14121027;
    public static final int DARK_OMEN_VI_TICK = 14121028;
    public static final int DOMINION_VI = 14121030;
    public static final int STYGIAN_COMMAND_MAIN = 14121031;
    public static final int SILENT_NIGHT = 14121032;
    public static final int SILENT_NIGHT_DART = 14121033;
    public static final int SILENT_NIGHT_PROJECTILE = 14121034;
    public static final int STYGIAN_COMMAND = 14121035;
    public static final int STYGIAN_COMMAND_FINISH = 14121036;

    public static final int[] V_VI_ACTIVE_SKILLS = {
        SHADOW_BITE,
        RAPID_THROW,
        DARK_OMEN_VI,
        DOMINION_VI,
        SILENT_NIGHT,
        STYGIAN_COMMAND
    };
}
