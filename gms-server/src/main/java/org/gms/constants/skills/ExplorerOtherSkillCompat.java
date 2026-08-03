package org.gms.constants.skills;

import java.util.Arrays;
import java.util.Map;

public final class ExplorerOtherSkillCompat {
    public record Replay(int skillId, int[] timesMs) {
    }

    private static final Map<Integer, Replay[]> MULTI_ATTACKS = Map.ofEntries(
            Map.entry(2121022, replays(replay(2121022, points(60, 120)))),
            Map.entry(2121032, replays(replay(2121032, range(2820, 60, 3780)))),
            Map.entry(2121035, replays(
                    replay(2121035, concat(range(1080, 60, 2100), points(2340))),
                    replay(2121036, range(2370, 30, 2940))
            )),
            Map.entry(2221027, replays(
                    replay(2221027, concat(
                            range(1320, 120, 2520), range(2610, 90, 3420),
                            range(3480, 60, 4080)
                    )),
                    replay(2221029, range(4110, 30, 4800))
            )),
            Map.entry(2221030, replays(replay(
                    2221030, concat(range(600, 60, 1080), range(1800, 30, 1890))
            ))),
            Map.entry(2321037, replays(
                    replay(2321037, concat(
                            points(30, 60, 90, 810), range(930, 120, 1170),
                            range(1260, 90, 1440), range(1500, 60, 1680),
                            range(1710, 30, 2010)
                    )),
                    replay(2321041, range(2040, 30, 3060))
            )),
            Map.entry(2321042, replays(
                    replay(2321042, range(660, 60, 1440)),
                    replay(2321043, range(1860, 30, 2220))
            )),
            Map.entry(3121029, replays(replay(3121029, concat(
                    range(660, 30, 930), range(2370, 120, 2850),
                    range(2940, 90, 3210), points(3270), range(3300, 30, 3840)
            )))),
            Map.entry(3121031, replays(replay(
                    3121031, concat(range(600, 60, 780), range(810, 30, 1140))
            ))),
            Map.entry(3221031, replays(replay(3221031, range(270, 180, 1170)))),
            Map.entry(3221032, replays(
                    replay(3221032, concat(
                            range(1020, 30, 1200), range(2820, 30, 3030),
                            range(3960, 30, 4110), range(4860, 30, 5070),
                            range(5460, 60, 5760)
                    )),
                    replay(3221033, concat(range(5820, 60, 6000), range(6030, 30, 6930)))
            )),
            Map.entry(3221034, replays(
                    replay(3221034, concat(range(1200, 30, 1500), points(1560))),
                    replay(3221035, range(2040, 30, 2370))
            )),
            Map.entry(4121026, replays(replay(4121026, concat(
                    range(1440, 30, 1980), range(2310, 30, 2520),
                    range(2580, 30, 2640), range(2760, 120, 3000)
            )))),
            Map.entry(4121028, replays(
                    replay(4121028, range(420, 30, 690)),
                    replay(4121029, range(1860, 30, 2190))
            )),
            Map.entry(4221036, replays(replay(4221036, range(180, 30, 840)))),
            Map.entry(4221039, replays(replay(4221039, concat(
                    range(540, 30, 630), range(1380, 30, 1590)
            )))),
            Map.entry(5121029, replays(
                    replay(5121029, range(2220, 120, 2580)),
                    replay(5121030, range(3780, 60, 5040))
            )),
            Map.entry(5121035, replays(
                    replay(5121035, range(420, 60, 960)),
                    replay(5121036, range(1740, 30, 2280))
            )),
            Map.entry(5221032, replays(replay(5221032, concat(
                    range(1020, 30, 1650), range(3030, 30, 3900)
            )))),
            Map.entry(5221034, replays(
                    replay(5221034, range(1320, 60, 1800)),
                    replay(5221035, range(1980, 60, 3060))
            ))
    );

    private ExplorerOtherSkillCompat() {
    }

    public static Replay[] multiAttacks(int skillId) {
        return MULTI_ATTACKS.get(skillId);
    }

    public static String videoLayer(int skillId) {
        return switch (skillId) {
            case 2121032, 2121035 -> "customSkill/fpArchMage/video" + skillId;
            case 2221027, 2221030 -> "customSkill/ilArchMage/video" + skillId;
            case 2321037, 2321042 -> "customSkill/bishop/video" + skillId;
            case 3121029, 3121031 -> "customSkill/bowmaster/video" + skillId;
            case 3221032, 3221034 -> "customSkill/marksman/video" + skillId;
            case 4121026, 4121028 -> "customSkill/nightLord/video" + skillId;
            case 4221036, 4221039 -> "customSkill/shadower/video" + skillId;
            case 5121029, 5121035 -> "customSkill/buccaneer/video" + skillId;
            case 5221032, 5221034 -> "customSkill/corsair/video" + skillId;
            default -> null;
        };
    }

    private static Replay replay(int skillId, int[] timesMs) {
        return new Replay(skillId, timesMs);
    }

    private static Replay[] replays(Replay... values) {
        return values;
    }

    private static int[] points(int... values) {
        return values;
    }

    private static int[] range(int first, int step, int last) {
        int[] result = new int[((last - first) / step) + 1];
        for (int index = 0; index < result.length; index++) {
            result[index] = first + (index * step);
        }
        return result;
    }

    private static int[] concat(int[]... values) {
        int length = Arrays.stream(values).mapToInt(value -> value.length).sum();
        int[] result = new int[length];
        int offset = 0;
        for (int[] value : values) {
            System.arraycopy(value, 0, result, offset, value.length);
            offset += value.length;
        }
        return result;
    }
}
