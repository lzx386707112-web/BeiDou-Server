package org.gms.constants.game;

public final class CharacterStance {
    public static final int WALK_RIGHT_STANCE = 2;
    public static final int WALK_LEFT_STANCE = 3;
    public static final int STAND_RIGHT_STANCE = 4;
    public static final int STAND_LEFT_STANCE = 5;
    public static final int JUMP_RIGHT_STANCE = 6;
    public static final int JUMP_LEFT_STANCE = 7;
    public static final int LADDER_RIGHT_STANCE = 14;
    public static final int LADDER_LEFT_STANCE = 15;
    public static final int ROPE_RIGHT_STANCE = 16;
    public static final int ROPE_LEFT_STANCE = 17;

    private CharacterStance() {
    }

    public static boolean isStanding(int stance) {
        return stance == STAND_RIGHT_STANCE || stance == STAND_LEFT_STANCE;
    }

    public static boolean isClimbing(int stance) {
        return stance == LADDER_RIGHT_STANCE || stance == LADDER_LEFT_STANCE
                || stance == ROPE_RIGHT_STANCE || stance == ROPE_LEFT_STANCE;
    }
}
