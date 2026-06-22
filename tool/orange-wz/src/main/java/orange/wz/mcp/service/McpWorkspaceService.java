package orange.wz.mcp.service;

import orange.wz.mcp.dto.NodeSummary;
import orange.wz.mcp.dto.NodeDetail;
import orange.wz.mcp.dto.NodeReference;
import orange.wz.mcp.dto.OverwriteStrategy;
import orange.wz.mcp.session.McpSessionState;
import orange.wz.provider.WzObject;
import orange.wz.provider.tools.wzkey.WzKey;

import java.io.File;
import java.util.List;
import java.util.Map;

public interface McpWorkspaceService {
    void loadFiles(McpSessionState session, List<File> files, WzKey key);

    void unloadNode(McpSessionState session, NodeReference reference);

    void unloadAll(McpSessionState session);

    NodeSummary createWz(McpSessionState session, String fileName, short version, WzKey key);

    NodeSummary createImg(McpSessionState session, String fileName, WzKey key);

    List<NodeSummary> listLoadedRoots(McpSessionState session);

    WzObject findNode(McpSessionState session, NodeReference reference, boolean autoParse);

    List<NodeSummary> listChildren(McpSessionState session, NodeReference reference, boolean autoParse);

    void copyNodes(McpSessionState session, List<NodeReference> sources, boolean autoParse);

    List<NodeSummary> pasteToNode(McpSessionState session, NodeReference target, OverwriteStrategy strategy, boolean autoParse);

    NodeSummary createChildNode(
            McpSessionState session,
            NodeReference parent,
            String type,
            String name,
            String value,
            Integer x,
            Integer y,
            String base64Png,
            String base64Mp3,
            String pngFormat,
            boolean autoParse
    );

    void deleteNode(McpSessionState session, NodeReference reference, boolean autoParse);

    List<NodeSummary> searchNodeByName(McpSessionState session, NodeReference start, String keyword, boolean autoParse);

    List<Map<String, Object>> searchNodeByValue(McpSessionState session, NodeReference start, String keyword, boolean autoParse);

    NodeDetail getNodeDetail(McpSessionState session, NodeReference reference, boolean autoParse);

    Map<String, Object> getNodeTreeJson(McpSessionState session, NodeReference reference, boolean autoParse, int maxDepth);

    List<Map<String, Object>> batchFindNodes(McpSessionState session, List<Map<String, Object>> queries);

    List<Map<String, Object>> batchUpdateNodes(McpSessionState session, List<Map<String, Object>> operations);

    void saveNode(McpSessionState session, NodeReference reference, boolean autoParse);

    void saveNodeAs(McpSessionState session, NodeReference reference, String filePath, boolean autoParse);
}
