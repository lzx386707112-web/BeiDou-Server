package orange.wz.provider.tools;

import java.util.Base64;

public final class Base64Tool {
    public static String coverBytesToBase64(byte[] bytes) {
        if (bytes == null) return "";
        return Base64.getEncoder().encodeToString(bytes);
    }

    public static byte[] coverBase64ToBytes(String base64) {
        if (base64 == null || base64.isBlank()) {
            return null;
        }

        return Base64.getDecoder().decode(base64);
    }
}
