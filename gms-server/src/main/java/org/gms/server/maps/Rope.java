package org.gms.server.maps;

public final class Rope {
    private final int x;
    private final int y1;
    private final int y2;
    private final boolean isLadder;

    public Rope(int x, int y1, int y2, boolean isLadder) {
        this.x = x;
        this.y1 = y1;
        this.y2 = y2;
        this.isLadder = isLadder;
    }

    public int x() {
        return x;
    }

    public int y1() {
        return y1;
    }

    public int y2() {
        return y2;
    }

    public boolean isLadder() {
        return isLadder;
    }

    public int topY() {
        return Math.min(y1, y2);
    }

    public int bottomY() {
        return Math.max(y1, y2);
    }
}
