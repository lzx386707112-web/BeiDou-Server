package orange.wz.provider;

public enum WzDirectoryType {
    UnknownType((byte) 1),
    RetrieveStringFromOffset((byte) 2),
    WzDirectory((byte) 3),
    WzImage((byte) 4);

    private final byte value;

    WzDirectoryType(byte value) {
        this.value = value;
    }

    public final byte getValue() {
        return value;
    }

    public static WzDirectoryType getByValue(byte value) {
        for (WzDirectoryType type : values()) {
            if (type.getValue() == value) {
                return type;
            }
        }
        return null;
    }
}
