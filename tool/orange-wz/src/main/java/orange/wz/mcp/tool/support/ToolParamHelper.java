package orange.wz.mcp.tool.support;

import orange.wz.mcp.dto.NodeReference;
import orange.wz.mcp.support.McpException;
import orange.wz.provider.tools.wzkey.WzKey;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

public final class ToolParamHelper {
    private ToolParamHelper() {
    }

    public static String requireString(Map<String, Object> params, String key) {
        Object value = params.get(key);
        if (value == null) {
            throw new McpException("缺少参数: " + key);
        }
        String text = String.valueOf(value);
        if (text.isBlank()) {
            throw new McpException("参数为空: " + key);
        }
        return text;
    }

    public static String getString(Map<String, Object> params, String key, String defaultValue) {
        Object value = params.get(key);
        if (value == null) return defaultValue;
        return String.valueOf(value);
    }

    public static boolean getBoolean(Map<String, Object> params, String key, boolean defaultValue) {
        Object value = params.get(key);
        if (value == null) return defaultValue;
        if (value instanceof Boolean b) return b;
        return Boolean.parseBoolean(String.valueOf(value));
    }

    public static short getShort(Map<String, Object> params, String key, short defaultValue) {
        Object value = params.get(key);
        if (value == null) return defaultValue;
        if (value instanceof Number n) return n.shortValue();
        return Short.parseShort(String.valueOf(value));
    }

    public static int getInt(Map<String, Object> params, String key, int defaultValue) {
        Object value = params.get(key);
        if (value == null) return defaultValue;
        if (value instanceof Number n) return n.intValue();
        return Integer.parseInt(String.valueOf(value));
    }

    public static UUID getSessionId(Map<String, Object> params) {
        String text = requireString(params, "sessionId");
        return UUID.fromString(text);
    }

    @SuppressWarnings("unchecked")
    public static List<String> getStringList(Map<String, Object> params, String key) {
        Object value = params.get(key);
        if (value == null) return List.of();
        if (value instanceof List<?> list) {
            List<String> result = new ArrayList<>();
            for (Object item : list) {
                if (item != null) result.add(String.valueOf(item));
            }
            return result;
        }
        return List.of(String.valueOf(value));
    }

    public static NodeReference getNodeReference(Map<String, Object> params) {
        return getNodeReference(params, "rootPath", "nodePath");
    }

    public static NodeReference getNodeReference(Map<String, Object> params, String rootKey, String nodeKey) {
        String rootPath = requireString(params, rootKey);
        String nodePath = getString(params, nodeKey, "");
        return new NodeReference(rootPath, nodePath);
    }

    @SuppressWarnings("unchecked")
    public static List<Map<String, Object>> getObjectList(Map<String, Object> params, String key) {
        Object value = params.get(key);
        if (value == null) {
            return List.of();
        }
        if (!(value instanceof List<?> list)) {
            throw new McpException("Parameter must be an array: " + key);
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object item : list) {
            if (!(item instanceof Map<?, ?> map)) {
                throw new McpException("Array item must be an object in: " + key);
            }
            result.add(new HashMap<>((Map<String, Object>) map));
        }
        return result;
    }

    @SuppressWarnings("unchecked")
    public static List<NodeReference> getNodeReferenceList(Map<String, Object> params, String key) {
        Object value = params.get(key);
        if (!(value instanceof List<?> list) || list.isEmpty()) {
            throw new McpException("Parameter must be a non-empty array: " + key);
        }
        List<NodeReference> result = new ArrayList<>();
        for (Object item : list) {
            if (!(item instanceof Map<?, ?> map)) {
                throw new McpException("Node reference must be an object in: " + key);
            }
            result.add(getNodeReference((Map<String, Object>) map));
        }
        return result;
    }

    public static List<File> getCanonicalLoadFiles(Map<String, Object> params, String key) {
        List<String> paths = getStringList(params, key);
        if (paths.isEmpty()) {
            throw new McpException("参数为空: " + key);
        }
        List<File> files = new ArrayList<>();
        for (String rawPath : paths) {
            if (rawPath == null || rawPath.isBlank()) {
                throw new McpException("路径不能为空");
            }
            try {
                File file = new File(rawPath).getCanonicalFile();
                if (!file.isAbsolute()) {
                    throw new McpException("路径必须是绝对路径: " + rawPath);
                }
                if (!file.exists()) {
                    throw new McpException("路径不存在: " + rawPath);
                }
                if (!file.isDirectory() && !isSupportedLoadFile(file)) {
                    throw new McpException("仅支持加载目录或 .wz/.img/.xml 文件: " + rawPath);
                }
                files.add(file);
            } catch (IOException e) {
                throw new McpException("无法解析路径: " + rawPath);
            }
        }
        return files;
    }

    @SuppressWarnings("unchecked")
    public static WzKey getWzKey(Map<String, Object> params, String key) {
        Object value = params.get(key);
        if (!(value instanceof Map<?, ?> map)) {
            throw new McpException("参数 " + key + " 必须是对象");
        }
        Map<String, Object> data = (Map<String, Object>) map;
        String name = requireString(data, "name");
        String ivBase64 = requireString(data, "ivBase64");
        String userKeyBase64 = requireString(data, "userKeyBase64");
        byte[] iv = Base64.getDecoder().decode(ivBase64);
        byte[] userKey = Base64.getDecoder().decode(userKeyBase64);
        return new WzKey(-1, name, iv, userKey);
    }

    private static boolean isSupportedLoadFile(File file) {
        String name = file.getName().toLowerCase(Locale.ROOT);
        return name.endsWith(".wz") || name.endsWith(".img") || name.endsWith(".xml");
    }
}
