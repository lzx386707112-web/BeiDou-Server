package orange.wz.provider.tools;

public final class StringTool {
    public static boolean isInteger(String s) {
        if (s == null || s.isBlank()) {
            return false;
        }
        try {
            Integer.parseInt(s);
            return true;
        } catch (NumberFormatException e) {
            return false;
        }
    }
}
