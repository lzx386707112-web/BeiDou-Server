package org.gms.server.life;

import java.util.Arrays;
import java.util.Optional;

public enum MobSkillType {
    ATTACK_UP(100),
    MAGIC_ATTACK_UP(101),
    DEFENSE_UP(102),
    MAGIC_DEFENSE_UP(103),
    ATTACK_UP_M(110),
    MAGIC_ATTACK_UP_M(111),
    DEFENSE_UP_M(112),
    MAGIC_DEFENSE_UP_M(113),
    HEAL_M(114),
    HASTE_M(115),
    SEAL(120),
    DARKNESS(121),
    WEAKNESS(122),
    STUN(123),
    CURSE(124),
    POISON(125),
    SLOW(126),
    DISPEL(127),
    SEDUCE(128),
    BANISH(129),
    AREA_POISON(131),
    REVERSE_INPUT(132),
    UNDEAD(133),
    STOP_POTION(134),
    STOP_MOTION(135),
    FEAR(136),
    CYGNUS_UNSUPPORTED_138(138),
    PHYSICAL_IMMUNE(140),
    MAGIC_IMMUNE(141),
    HARD_SKIN(142),
    PHYSICAL_COUNTER(143),
    MAGIC_COUNTER(144),
    PHYSICAL_AND_MAGIC_COUNTER(145),
    CYGNUS_UNSUPPORTED_146(146),
    PAD(150),
    MAD(151),
    PDR(152),
    MDR(153),
    ACC(154),
    EVA(155),
    SPEED(156),
    SEAL_SKILL(157),
    SUMMON_170(170),
    CYGNUS_UNSUPPORTED_171(171),
    CYGNUS_UNSUPPORTED_172(172),
    AKAYRUM_BLACK_HOLE_VISUAL(174),
    AKAYRUM_SCREEN_CRACK_VISUAL(176),
    AKAYRUM_GREEN_ORB_VISUAL(177),
    WILL_WEB_BURST(183),
    MAGNUS_METEOR_STORM(184),
    LUCID_DREAM_BURST(185),
    SUMMON_186(186),
    SEREN_SACRED_BURST(187),
    SUMMON_188(188),
    SUMMON_189(189),
    SUMMON_190(190),
    SUMMON_191(191),
    SUMMON(200),
    SUMMON_201(201),
    SUMMON_202(202),
    SUMMON_203(203);

    private final int id;

    MobSkillType(int id) {
        this.id = id;
    }

    public static Optional<MobSkillType> from(int id) {
        if (isOutOfIdRange(id)) {
            return Optional.empty();
        }

        return Arrays.stream(values())
                .filter(type -> type.getId() == id)
                .findAny();
    }

    private static boolean isOutOfIdRange(int id) {
        return id < 100 || id > 203;
    }

    public int getId() {
        return id;
    }
}
