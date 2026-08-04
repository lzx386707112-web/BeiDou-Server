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
package org.gms.client;

import lombok.Getter;
import org.gms.util.I18nUtil;


public enum Job {
    BEGINNER(0, I18nUtil.getMessage("job.name.0")),
    WARRIOR(100, I18nUtil.getMessage("job.name.100")),
    FIGHTER(110, I18nUtil.getMessage("job.name.110")), CRUSADER(111, I18nUtil.getMessage("job.name.111")), HERO(112, I18nUtil.getMessage("job.name.112")),
    PAGE(120, I18nUtil.getMessage("job.name.120")), WHITEKNIGHT(121, I18nUtil.getMessage("job.name.121")), PALADIN(122,  I18nUtil.getMessage("job.name.122")),
    SPEARMAN(130,  I18nUtil.getMessage("job.name.130")), DRAGONKNIGHT(131,  I18nUtil.getMessage("job.name.131")), DARKKNIGHT(132, I18nUtil.getMessage("job.name.132")),

    MAGICIAN(200, I18nUtil.getMessage("job.name.200")),
    FP_WIZARD(210, I18nUtil.getMessage("job.name.210")), FP_MAGE(211, I18nUtil.getMessage("job.name.211")), FP_ARCHMAGE(212, I18nUtil.getMessage("job.name.212")),
    IL_WIZARD(220, I18nUtil.getMessage("job.name.220")), IL_MAGE(221, I18nUtil.getMessage("job.name.221")), IL_ARCHMAGE(222, I18nUtil.getMessage("job.name.222")),
    CLERIC(230, I18nUtil.getMessage("job.name.230")), PRIEST(231, I18nUtil.getMessage("job.name.231")), BISHOP(232, I18nUtil.getMessage("job.name.232")),

    BOWMAN(300, I18nUtil.getMessage("job.name.300")),
    HUNTER(310, I18nUtil.getMessage("job.name.310")), RANGER(311, I18nUtil.getMessage("job.name.311")), BOWMASTER(312, I18nUtil.getMessage("job.name.312")),
    CROSSBOWMAN(320, I18nUtil.getMessage("job.name.320")), SNIPER(321, I18nUtil.getMessage("job.name.321")), MARKSMAN(322, I18nUtil.getMessage("job.name.322")),

    THIEF(400, I18nUtil.getMessage("job.name.400")),
    ASSASSIN(410,I18nUtil.getMessage("job.name.410")), HERMIT(411, I18nUtil.getMessage("job.name.411")), NIGHTLORD(412, I18nUtil.getMessage("job.name.412")),
    BANDIT(420, I18nUtil.getMessage("job.name.420")), CHIEFBANDIT(421, I18nUtil.getMessage("job.name.421")), SHADOWER(422, I18nUtil.getMessage("job.name.422")),

    PIRATE(500, I18nUtil.getMessage("job.name.500")),
    BRAWLER(510, I18nUtil.getMessage("job.name.510")), MARAUDER(511, I18nUtil.getMessage("job.name.511")), BUCCANEER(512, I18nUtil.getMessage("job.name.512")),
    GUNSLINGER(520, I18nUtil.getMessage("job.name.520")), OUTLAW(521, I18nUtil.getMessage("job.name.521")), CORSAIR(522, I18nUtil.getMessage("job.name.522")),

    MAPLELEAF_BRIGADIER(800, I18nUtil.getMessage("job.name.800")),
    GM(900, I18nUtil.getMessage("job.name.900")), SUPERGM(910, I18nUtil.getMessage("job.name.910")),

    NOBLESSE(1000, I18nUtil.getMessage("job.name.1000")),
    DAWNWARRIOR1(1100, I18nUtil.getMessage("job.name.1100")), DAWNWARRIOR2(1110, I18nUtil.getMessage("job.name.1110")), DAWNWARRIOR3(1111, I18nUtil.getMessage("job.name.1111")), DAWNWARRIOR4(1112, I18nUtil.getMessage("job.name.1112")),
    BLAZEWIZARD1(1200, I18nUtil.getMessage("job.name.1200")), BLAZEWIZARD2(1210, I18nUtil.getMessage("job.name.1210")), BLAZEWIZARD3(1211,I18nUtil.getMessage("job.name.1211")), BLAZEWIZARD4(1212,I18nUtil.getMessage("job.name.1212")),
    WINDARCHER1(1300,I18nUtil.getMessage("job.name.1300")), WINDARCHER2(1310, I18nUtil.getMessage("job.name.1310")), WINDARCHER3(1311, I18nUtil.getMessage("job.name.1311")), WINDARCHER4(1312, I18nUtil.getMessage("job.name.1312")),
    NIGHTWALKER1(1400,I18nUtil.getMessage("job.name.1400")), NIGHTWALKER2(1410,I18nUtil.getMessage("job.name.1410")), NIGHTWALKER3(1411,I18nUtil.getMessage("job.name.1411")), NIGHTWALKER4(1412,I18nUtil.getMessage("job.name.1412")),
    THUNDERBREAKER1(1500,I18nUtil.getMessage("job.name.1500")), THUNDERBREAKER2(1510,I18nUtil.getMessage("job.name.1510")), THUNDERBREAKER3(1511,I18nUtil.getMessage("job.name.1511")), THUNDERBREAKER4(1512,I18nUtil.getMessage("job.name.1512")),

    LEGEND(2000, I18nUtil.getMessage("job.name.2000")), EVAN(2001, I18nUtil.getMessage("job.name.2001")),
    ARAN1(2100, I18nUtil.getMessage("job.name.2100")), ARAN2(2110, I18nUtil.getMessage("job.name.2110")), ARAN3(2111, I18nUtil.getMessage("job.name.2111")), ARAN4(2112, I18nUtil.getMessage("job.name.2112")),

    EVAN1(2200,I18nUtil.getMessage("job.name.2200")), EVAN2(2210, I18nUtil.getMessage("job.name.2210")), EVAN3(2211, I18nUtil.getMessage("job.name.2211")), EVAN4(2212, I18nUtil.getMessage("job.name.2212")), EVAN5(2213, I18nUtil.getMessage("job.name.2213")), EVAN6(2214, I18nUtil.getMessage("job.name.2214")),
    EVAN7(2215, I18nUtil.getMessage("job.name.2215")), EVAN8(2216, I18nUtil.getMessage("job.name.2216")), EVAN9(2217, I18nUtil.getMessage("job.name.2217")), EVAN10(2218, I18nUtil.getMessage("job.name.2218"));

    @Getter
    private final int id;
    @Getter
    private final String name;

    final static int maxId = 22;    // maxId = (EVAN / 100);

    Job(int id, String name) {
        this.id = id;
        this.name = name;
    }


    public static int getMax() {
        return maxId;
    }

    public static Job getById(int id) {
        for (Job l : Job.values()) {
            if (l.getId() == id) {
                return l;
            }
        }
        return BEGINNER;
    }

    public static Job getBy5ByteEncoding(int encoded) {
        return switch (encoded) {
            case 2 -> WARRIOR;
            case 4 -> MAGICIAN;
            case 8 -> BOWMAN;
            case 16 -> THIEF;
            case 32 -> PIRATE;
            case 1024 -> NOBLESSE;
            case 2048 -> DAWNWARRIOR1;
            case 4096 -> BLAZEWIZARD1;
            case 8192 -> WINDARCHER1;
            case 16384 -> NIGHTWALKER1;
            case 32768 -> THUNDERBREAKER1;
            default -> BEGINNER;
        };
    }

    public boolean isA(Job basejob) {  // thanks Steve (kaito1410) for pointing out an improvement here
        int basebranch = basejob.getId() / 10;
        return (getId() / 10 == basebranch && getId() >= basejob.getId()) || (basebranch % 10 == 0 && getId() / 100 == basejob.getId() / 100);
    }

    public int getJobNiche() {
        return (id / 100) % 10;
        
        /*
        case 0: BEGINNER;
        case 1: WARRIOR;
        case 2: MAGICIAN;
        case 3: BOWMAN;  
        case 4: THIEF;
        case 5: PIRATE;
        */
    }

    public int getJobTier() {
        if (id == 0) {
            return 0;
        }

        int lastTwoDigits = id % 100;
        return switch (lastTwoDigits) {
            case 0 -> 1;
            case 10, 20, 30 -> 2;
            case 11, 21, 31 -> 3;
            case 12, 22, 32 -> 4;
            default -> 0;
        };
    }

    public static Job getJobStyleInternal(int jobid, byte opt) {
        int jobtype = jobid / 100;

        if (jobtype == WARRIOR.getId() / 100 || jobtype == DAWNWARRIOR1.getId() / 100 || jobtype == ARAN1.getId() / 100) {
            return WARRIOR;
        } else if (jobtype == MAGICIAN.getId() / 100 || jobtype == BLAZEWIZARD1.getId() / 100 || jobtype == EVAN1.getId() / 100) {
            return MAGICIAN;
        } else if (jobtype == BOWMAN.getId() / 100 || jobtype == WINDARCHER1.getId() / 100) {
            if (jobid / 10 == CROSSBOWMAN.getId() / 10) {
                return CROSSBOWMAN;
            } else {
                return BOWMAN;
            }
        } else if (jobtype == THIEF.getId() / 100 || jobtype == NIGHTWALKER1.getId() / 100) {
            return THIEF;
        } else if (jobtype == PIRATE.getId() / 100 || jobtype == THUNDERBREAKER1.getId() / 100) {
            if (opt == (byte) 0x80) {
                return BRAWLER;
            } else {
                return GUNSLINGER;
            }
        }

        return BEGINNER;
    }

    /**
     * 根据等级变更角色职业（以冰雷法师系列为例，其他职业同理扩展）
     *
     * @param currentJob 当前职业
     * @param level      角色等级
     * @return 变更后的职业
     */
    public static Job changeJobByLevel(Job currentJob, int level) {
        Job baseJobType = getBaseJobType(currentJob);

        // 处理冰雷魔法师分支（220系列）
        if (baseJobType.isA(Job.IL_WIZARD)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) { // 8-30级为魔法师
                return Job.MAGICIAN;
            } else if (level < 70) { // 31-69级为冰雷法师
                return Job.IL_WIZARD;
            } else if (level < 120) { // 70-119级为冰雷巫师
                return Job.IL_MAGE;
            } else { // 120级及以上为冰雷魔导士
                return Job.IL_ARCHMAGE;
            }
        }

        // 处理火毒魔法师分支（210系列）
        if (baseJobType.isA(Job.FP_WIZARD)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) {
                return Job.MAGICIAN;
            } else if (level < 70) {
                return Job.FP_WIZARD;
            } else if (level < 120) {
                return Job.FP_MAGE;
            } else {
                return Job.FP_ARCHMAGE;
            }
        }

        // 处理牧师分支（230系列）
        if (baseJobType.isA(Job.CLERIC)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) {
                return Job.MAGICIAN;
            } else if (level < 70) {
                return Job.CLERIC;
            } else if (level < 120) {
                return Job.PRIEST;
            } else {
                return Job.BISHOP;
            }
        }
        // 处理战士-剑客分支（110系列）
        if (baseJobType.isA(Job.FIGHTER)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) {
                return Job.WARRIOR;
            } else if (level < 70) {
                return Job.FIGHTER;
            } else if (level < 120) {
                return Job.CRUSADER;
            } else {
                return Job.HERO;
            }
        }

        // 处理战士-准骑士分支（120系列）
        if (baseJobType.isA(Job.PAGE)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) {
                return Job.WARRIOR;
            } else if (level < 70) {
                return Job.PAGE;
            } else if (level < 120) {
                return Job.WHITEKNIGHT;
            } else {
                return Job.PALADIN;
            }
        }

        // 处理战士-枪战士分支（130系列）
        if (baseJobType.isA(Job.SPEARMAN)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) {
                return Job.WARRIOR;
            } else if (level < 70) {
                return Job.SPEARMAN;
            } else if (level < 120) {
                return Job.DRAGONKNIGHT;
            } else {
                return Job.DARKKNIGHT;
            }
        }

        // 处理弓箭手-猎人分支（310系列）
        if (baseJobType.isA(Job.HUNTER)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) {
                return Job.BOWMAN;
            } else if (level < 70) {
                return Job.HUNTER;
            } else if (level < 120) {
                return Job.RANGER;
            } else {
                return Job.BOWMASTER;
            }
        }

        // 处理弓箭手-弩弓手分支（320系列）
        if (baseJobType.isA(Job.CROSSBOWMAN)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) {
                return Job.BOWMAN;
            } else if (level < 70) {
                return Job.CROSSBOWMAN;
            } else if (level < 120) {
                return Job.SNIPER;
            } else {
                return Job.MARKSMAN;
            }
        }

        // 处理飞侠-刺客分支（410系列）
        if (baseJobType.isA(Job.ASSASSIN)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) {
                return Job.THIEF;
            } else if (level < 70) {
                return Job.ASSASSIN;
            } else if (level < 120) {
                return Job.HERMIT;
            } else {
                return Job.NIGHTLORD;
            }
        }

        // 处理飞侠-侠客分支（420系列）
        if (baseJobType.isA(Job.BANDIT)) {
            if (level < 8) {
                return Job.BEGINNER;
            } else if (level < 31) {
                return Job.THIEF;
            } else if (level < 70) {
                return Job.BANDIT;
            } else if (level < 120) {
                return Job.CHIEFBANDIT;
            } else {
                return Job.SHADOWER;
            }
        }

        // 处理骑士团-魂骑士分支（1100系列）
        if (baseJobType.isA(Job.DAWNWARRIOR1)) {
            if (level < 10) {
                return Job.NOBLESSE;
            } else if (level < 30) {
                return Job.DAWNWARRIOR1;
            } else if (level < 70) {
                return Job.DAWNWARRIOR2;
            } else if (level < 120) {
                return Job.DAWNWARRIOR3;
            } else {
                return Job.DAWNWARRIOR4;
            }
        }

        // 处理骑士团-炎术士分支（1100系列）
        if (baseJobType.isA(Job.BLAZEWIZARD1)) {
            if (level < 10) {
                return Job.NOBLESSE;
            } else if (level < 30) {
                return Job.BLAZEWIZARD1;
            } else if (level < 70) {
                return Job.BLAZEWIZARD2;
            } else if (level < 120) {
                return Job.BLAZEWIZARD3;
            } else {
                return Job.BLAZEWIZARD4;
            }
        }

        // 处理骑士团-风箭手分支（1100系列）
        if (baseJobType.isA(Job.WINDARCHER1)) {
            if (level < 10) {
                return Job.NOBLESSE;
            } else if (level < 30) {
                return Job.WINDARCHER1;
            } else if (level < 70) {
                return Job.WINDARCHER2;
            } else if (level < 120) {
                return Job.WINDARCHER3;
            } else {
                return Job.WINDARCHER4;
            }
        }

        // 处理骑士团-夜行分支（1100系列）
        if (baseJobType.isA(Job.NIGHTWALKER1)) {
            if (level < 10) {
                return Job.NOBLESSE;
            } else if (level < 30) {
                return Job.NIGHTWALKER1;
            } else if (level < 70) {
                return Job.NIGHTWALKER2;
            } else if (level < 120) {
                return Job.NIGHTWALKER3;
            } else {
                return Job.NIGHTWALKER4;
            }
        }

        // 处理骑士团-奇袭分支（1100系列）
        if (baseJobType.isA(Job.THUNDERBREAKER1)) {
            if (level < 10) {
                return Job.NOBLESSE;
            } else if (level < 30) {
                return Job.THUNDERBREAKER1;
            } else if (level < 70) {
                return Job.THUNDERBREAKER2;
            } else if (level < 120) {
                return Job.THUNDERBREAKER3;
            } else {
                return Job.THUNDERBREAKER4;
            }
        }

        // 处理战神分支（2100系列）
        if (baseJobType.isA(Job.LEGEND)) {
            if (level < 10) {
                return Job.LEGEND;
            } else if (level < 30) {
                return Job.ARAN1;
            } else if (level < 70) {
                return Job.ARAN2;
            } else if (level < 120) {
                return Job.ARAN3;
            } else {
                return Job.ARAN4;
            }
        }


        // 默认返回当前职业
        return currentJob;
    }


    /**
     * 获取职业所属的基础体系（如冰雷魔导师属于法师系）
     */
    public static Job getBaseJobType(Job job) {
        if (job.isTargetJob(Job.FIGHTER)) {
            return Job.FIGHTER;
        } else if (job.isTargetJob(Job.PAGE)) {
            return Job.PAGE;
        } else if (job.isTargetJob(Job.SPEARMAN)) {
            return Job.SPEARMAN;
        } else if (job.isTargetJob(Job.MAGICIAN)) {
            return Job.MAGICIAN;
        } else if (job.isTargetJob(Job.FP_WIZARD)) {
            return Job.FP_WIZARD;
        } else if (job.isTargetJob(Job.IL_WIZARD)) {
            return Job.IL_WIZARD;
        } else if (job.isTargetJob(Job.CLERIC)) {
            return Job.CLERIC;
        } else if (job.isTargetJob(Job.BOWMAN)) {
            return Job.BOWMAN;
        } else if (job.isTargetJob(Job.HUNTER)) {
            return Job.HUNTER;
        } else if (job.isTargetJob(Job.CROSSBOWMAN)) {
            return Job.CROSSBOWMAN;
        } else if (job.isTargetJob(Job.THIEF)) {
            return Job.THIEF;
        } else if (job.isTargetJob(Job.ASSASSIN)) {
            return Job.ASSASSIN;
        } else if (job.isTargetJob(Job.BANDIT)) {
            return Job.BANDIT;
        } else if (job.isTargetJob(Job.PIRATE)) {
            return Job.PIRATE;
        } else if (job.isTargetJob(Job.BRAWLER)) {
            return Job.BRAWLER;
        } else if (job.isTargetJob(Job.GUNSLINGER)) {
            return Job.GUNSLINGER;
        } else if (job.isTargetJob(Job.DAWNWARRIOR1)) {
            return Job.DAWNWARRIOR1;
        } else if (job.isTargetJob(Job.BLAZEWIZARD1)) {
            return Job.BLAZEWIZARD1;
        } else if (job.isTargetJob(Job.WINDARCHER1)) {
            return Job.WINDARCHER1;
        } else if (job.isTargetJob(Job.NIGHTWALKER1)) {
            return Job.NIGHTWALKER1;
        } else if (job.isTargetJob(Job.THUNDERBREAKER1)) {
            return Job.THUNDERBREAKER1;
        } else if (job.isTargetJob(Job.LEGEND)) {
            return Job.LEGEND;
        } else {
            return job;
        }
    }

    public boolean isTargetJob(Job basejob) {
        int baseJobId = basejob.getId();
        int curId = getId();
        if (baseJobId >= 1000) {
            return baseJobId / 100 == curId / 100;
        }
        return baseJobId / 10 == curId / 10;
    }


}

