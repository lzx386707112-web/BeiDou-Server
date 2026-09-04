package org.gms.server.weather;

public enum WeatherRegion {
    EL_NATH(WeatherProfile.SNOW, 0x41508E), RIEN(WeatherProfile.SNOW, 0x485294),
    MUSHROOM_SHRINE(WeatherProfile.BLOSSOM, 0x605492),
    ELLINIA(weights(1,3,1,1.5,2.5,1,1,0,0), 0x3D666C),
    PERION(weights(1,.1,.5,.6,.1,.5,1,0,0), 0x635582),
    KERNING_CITY(weights(.7,1.4,1,2,1,1,.8,0,0), 0x6E4A7E),
    SHOWA(weights(.7,1.9,.8,1.7,1,.6,.8,0,0), 0x74497A),
    ORBIS(weights(.6,1.8,1.2,1.6,2.6,1,.6,0,0), 0x6A5090),
    MU_LUNG(weights(.8,1.3,1,2,.6,.8,1.2,0,0), 0x6B4E84),
    ARIANT(weights(1.6,.05,0,.3,.05,0,.2,0,5), 0x6E5078),
    SLEEPYWOOD(weights(.9,1.2,.8,1.8,.4,.5,1.2,0,0), 0x2E3857),
    AQUA_ROAD(WeatherProfile.CLEAR, 0x354165),
    LEAFRE(weights(.8,1.7,.6,1.3,1.6,.4,1.5,0,0), 0x3A5E58),
    LUDIBRIUM(weights(1.5,.7,1,.8,.3,.8,.7,0,0), 0x574C90),
    FLORINA(weights(1.4,1.3,0,.5,1.2,0,.3,0,0), 0x40646E),
    AMORIA(weights(1.6,.5,.6,.4,.2,.4,.6,2,0), 0x5E5490),
    LITH_HARBOUR(weights(.7,1.6,1,1.6,1.8,1,.7,0,0), 0x44607E),
    MAGATIA(weights(1.4,.1,0,1.6,.1,0,.3,0,0), 0x465A85),
    NAUTILUS(weights(.6,1.8,.6,1.8,2.2,.5,.4,0,0), 0x46587F),
    HENESYS(weights(1.3,.9,.7,.7,.4,.5,1.8,0,0), 0x4C5C88),
    EREVE(weights(1.5,1.1,.4,.8,.6,.3,.9,0,0), 0x4E5A96),
    TEMPLE_OF_TIME(weights(.8,.4,.3,2.6,.2,.2,.4,0,0), 0x554A8C),
    ELLIN_FOREST(weights(.7,2.2,.4,1.6,1.4,.2,1.7,0,0), 0x3C5E5C),
    NEW_LEAF_CITY(weights(.7,1.6,.9,1.9,1.1,.7,.7,0,0), 0x6E4A7E),
    FORMOSA(weights(1.2,1.6,.1,.9,1.5,0,.8,0,0), 0x445C7E),
    ZIPANGU(weights(.9,1.4,.9,1.7,.7,.6,1.3,0,0), 0x4A5490),
    DEFAULT(weights(1,1,1,1,1,1,1,0,0), 0x4A5A8C);

    private final WeatherProfile forcedProfile;
    private final double[] weights;
    private final int tint;

    WeatherRegion(WeatherProfile forcedProfile, int tint) {
        this(forcedProfile, weights(1, 0, 0, 0, 0, 0, 0, 0, 0), tint);
    }

    WeatherRegion(double[] weights, int tint) {
        this(null, weights, tint);
    }

    WeatherRegion(WeatherProfile forcedProfile, double[] weights, int tint) {
        this.forcedProfile = forcedProfile;
        this.weights = weights;
        this.tint = tint;
    }

    public WeatherProfile forcedProfile() { return forcedProfile; }
    public double[] weights() { return weights.clone(); }
    public int tint() { return tint; }
    public int paletteId() { return ordinal(); }

    private static double[] weights(double... values) { return values; }

    public static WeatherRegion forMap(int mapId) {
        if (mapId < 0) return DEFAULT;
        return switch (mapId / 1_000_000) {
            case 100 -> HENESYS; case 101 -> ELLINIA; case 102 -> PERION;
            case 103 -> KERNING_CITY; case 104 -> LITH_HARBOUR; case 105 -> SLEEPYWOOD;
            case 110 -> FLORINA; case 120 -> NAUTILUS; case 130 -> EREVE; case 140 -> RIEN;
            case 200 -> ORBIS; case 211 -> EL_NATH; case 220, 221, 222 -> LUDIBRIUM;
            case 230 -> AQUA_ROAD; case 240 -> LEAFRE; case 250, 251 -> MU_LUNG;
            case 260 -> ARIANT; case 261 -> MAGATIA; case 270 -> TEMPLE_OF_TIME;
            case 300 -> ELLIN_FOREST; case 600, 610 -> NEW_LEAF_CITY; case 680 -> AMORIA;
            case 740, 741, 742 -> FORMOSA;
            case 800 -> mapId == 800000000 ? MUSHROOM_SHRINE : ZIPANGU;
            case 801 -> SHOWA; default -> DEFAULT;
        };
    }
}
