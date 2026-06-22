package orange.wz.mcp.resolve;

import orange.wz.mcp.dto.NodeReference;
import orange.wz.mcp.support.McpException;
import orange.wz.provider.WzDirectory;
import orange.wz.provider.WzFolder;
import orange.wz.provider.WzImage;
import orange.wz.provider.WzImageFile;
import orange.wz.provider.WzImageProperty;
import orange.wz.provider.WzObject;
import orange.wz.provider.WzXmlFile;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class NodePathResolver {
    private static final Pattern INDEXED_SEGMENT = Pattern.compile("^(.*)\\[(\\d+)]$");

    public WzObject resolveFromRoots(List<WzObject> roots, NodeReference reference, boolean autoParse) {
        if (reference == null) {
            throw new McpException("节点引用不能为空");
        }
        WzObject current = resolveRoot(roots, reference.rootPath());
        if (reference.nodePath().isBlank()) {
            return current;
        }

        String[] parts = reference.nodePath().split("/");
        for (String part : parts) {
            if (part.isBlank()) {
                continue;
            }
            current = findChild(current, part, autoParse, reference);
            if (current == null) {
                throw new McpException("节点路径不存在: rootPath=" + reference.rootPath() + ", nodePath=" + reference.nodePath());
            }
        }
        return current;
    }

    public WzObject resolveRoot(List<WzObject> roots, String rootPath) {
        if (rootPath == null || rootPath.isBlank()) {
            throw new McpException("rootPath 不能为空");
        }
        String expected = normalizeRootPath(rootPath);
        List<WzObject> matches = new ArrayList<>();
        for (WzObject root : roots) {
            String actual = rootPathOf(root);
            if (actual != null && sameRootPath(actual, expected)) {
                matches.add(root);
            }
        }
        if (matches.isEmpty()) {
            throw new McpException("找不到根节点: " + rootPath);
        }
        if (matches.size() > 1) {
            throw new McpException("rootPath 命中多个根节点: " + rootPath);
        }
        return matches.getFirst();
    }

    private WzObject findChild(WzObject parent, String segment, boolean autoParse, NodeReference reference) {
        List<WzObject> children = getChildren(parent, autoParse);
        if (children.isEmpty()) {
            return null;
        }

        SegmentSelector selector = parseSegment(segment);
        List<WzObject> matches = children.stream()
                .filter(child -> child.getName().equalsIgnoreCase(selector.name()))
                .toList();
        if (matches.isEmpty()) {
            return null;
        }
        if (selector.index() != null) {
            int index = selector.index();
            if (index < 0 || index >= matches.size()) {
                throw new McpException("同名节点索引越界: " + segment);
            }
            return matches.get(index);
        }
        if (matches.size() > 1) {
            throw new McpException("nodePath 命中多个同名节点，请使用 name[index] 指定序号: rootPath="
                    + reference.rootPath() + ", nodePath=" + reference.nodePath() + ", segment=" + segment);
        }
        return matches.getFirst();
    }

    private List<WzObject> getChildren(WzObject parent, boolean autoParse) {
        if (parent instanceof WzFolder folder) {
            return folder.getChildren();
        }
        if (parent instanceof WzDirectory dir) {
            if (dir.isWzFile() && autoParse && !dir.getWzFile().parse()) {
                throw new McpException("WZ 文件解析失败: " + dir.getName());
            }
            return dir.getChildren();
        }
        if (parent instanceof WzImage image) {
            if (autoParse && !image.parse()) {
                throw new McpException("IMG 解析失败: " + image.getName());
            }
            return new ArrayList<>(image.getChildren());
        }
        if (parent instanceof WzImageProperty prop && prop.isListProperty()) {
            return new ArrayList<>(prop.getChildren());
        }
        return List.of();
    }

    private SegmentSelector parseSegment(String segment) {
        Matcher matcher = INDEXED_SEGMENT.matcher(segment);
        if (!matcher.matches()) {
            return new SegmentSelector(segment, null);
        }
        return new SegmentSelector(matcher.group(1), Integer.parseInt(matcher.group(2)));
    }

    public static String rootPathOf(WzObject obj) {
        WzObject root = rootOf(obj);
        return switch (root) {
            case null -> null;
            case WzFolder folder -> normalizeRootPath(folder.getFilePath());
            case WzDirectory dir when dir.isWzFile() -> normalizeRootPath(dir.getWzFile().getFilePath());
            case WzImageFile imageFile -> normalizeRootPath(imageFile.getFilePath());
            case WzXmlFile xmlFile -> normalizeRootPath(xmlFile.getFilePath());
            default -> normalizeRootPath(root.getPath());
        };
    }

    public static String nodePathOf(WzObject obj) {
        WzObject root = rootOf(obj);
        if (root == null || root == obj) {
            return "";
        }

        List<String> segments = new ArrayList<>();
        WzObject current = obj;
        while (current != null && current != root) {
            segments.addFirst(segmentOf(current));
            current = current.getParent();
        }
        return String.join("/", segments);
    }

    public static String displayPathOf(WzObject obj) {
        WzObject root = rootOf(obj);
        if (root == null) {
            return obj == null ? "" : obj.getPath();
        }
        String nodePath = nodePathOf(obj);
        if (nodePath.isBlank()) {
            return root.getName();
        }
        return root.getName() + "/" + nodePath;
    }

    private static String segmentOf(WzObject obj) {
        WzObject parent = obj.getParent();
        if (parent == null) {
            return obj.getName();
        }
        List<WzObject> siblings = childrenWithoutParsing(parent);
        List<WzObject> sameName = siblings.stream()
                .filter(item -> item.getName().equalsIgnoreCase(obj.getName()))
                .toList();
        if (sameName.size() <= 1) {
            return obj.getName();
        }
        int index = sameName.indexOf(obj);
        return obj.getName() + "[" + Math.max(index, 0) + "]";
    }

    public static WzObject rootOf(WzObject obj) {
        if (obj == null) {
            return null;
        }
        WzObject current = obj;
        while (current.getParent() != null) {
            if (current instanceof WzDirectory dir && dir.isWzFile()) {
                return current;
            }
            current = current.getParent();
        }
        return current;
    }

    public static String normalizeRootPath(String rootPath) {
        if (rootPath == null || rootPath.isBlank()) {
            return rootPath;
        }
        return Path.of(rootPath).toAbsolutePath().normalize().toString();
    }

    public static boolean sameRootPath(String left, String right) {
        if (left == null || right == null) {
            return Objects.equals(left, right);
        }
        return normalizeRootPath(left).toLowerCase(Locale.ROOT)
                .equals(normalizeRootPath(right).toLowerCase(Locale.ROOT));
    }

    private static List<WzObject> childrenWithoutParsing(WzObject parent) {
        if (parent instanceof WzFolder folder) {
            return folder.getChildren();
        }
        if (parent instanceof WzDirectory dir) {
            return dir.getChildren();
        }
        if (parent instanceof WzImage image) {
            return new ArrayList<>(image.getChildren());
        }
        if (parent instanceof WzImageProperty prop && prop.isListProperty()) {
            return new ArrayList<>(prop.getChildren());
        }
        return List.of();
    }

    private record SegmentSelector(String name, Integer index) {
    }
}
