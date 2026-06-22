package orange.wz.provider.properties;

import orange.wz.provider.WzAESConstant;
import orange.wz.provider.WzImage;
import orange.wz.provider.WzImageProperty;
import orange.wz.provider.WzObject;
import orange.wz.provider.tools.BinaryWriter;
import orange.wz.provider.tools.WzMutableKey;
import orange.wz.provider.tools.WzType;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;

public class WzLuaProperty extends WzImageProperty {
    private byte[] encryptedBytes;
    public static final WzMutableKey luaKey = new WzMutableKey(WzAESConstant.WZ_CMS_IV, WzAESConstant.DEFAULT_KEY);

    public String getString() {
        byte[] decodedBytes = encodeDecode(encryptedBytes);
        return new String(decodedBytes, StandardCharsets.UTF_8);
    }

    public void setString(String string) {
        byte[] decodedBytes = string.getBytes(StandardCharsets.UTF_8);
        encryptedBytes = encodeDecode(decodedBytes);
    }

    public byte[] encodeDecode(byte[] input) {
        int len = input.length;
        byte[] newBytes = new byte[len];
        for (int i = 0; i < len; i++) {
            newBytes[i] = (byte) (input[i] ^ luaKey.get(i));
        }
        return newBytes;
    }

    public WzLuaProperty(String name, byte[] encryptedBytes, WzObject parent, WzImage wzImage) {
        super(name, WzType.LUA_PROPERTY, parent, wzImage);
        this.encryptedBytes = Arrays.copyOf(encryptedBytes, encryptedBytes.length);
    }

    @Override
    public void writeValue(BinaryWriter writer) {
        writer.putByte((byte) WzImage.withLuaFlag);
        writer.writeCompressedInt(encryptedBytes.length);
        writer.putBytes(encryptedBytes);
    }

    @Override
    public WzLuaProperty deepClone(WzObject parent) {
        return new WzLuaProperty(name, Arrays.copyOf(encryptedBytes, encryptedBytes.length), parent, null);
    }
}
