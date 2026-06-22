package orange.wz.mcp.dto;

public record NodeReference(
        String rootPath,
        String nodePath
) {
    public NodeReference {
        nodePath = normalizeNodePath(nodePath);
    }

    private static String normalizeNodePath(String value) {
        if (value == null || value.isBlank()) {
            return "";
        }
        String normalized = value.trim().replace('\\', '/');
        while (normalized.startsWith("/")) {
            normalized = normalized.substring(1);
        }
        while (normalized.endsWith("/")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        return normalized;
    }
}
