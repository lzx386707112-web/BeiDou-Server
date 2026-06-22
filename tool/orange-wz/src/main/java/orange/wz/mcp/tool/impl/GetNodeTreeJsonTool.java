package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;
import orange.wz.mcp.tool.support.ToolParamHelper;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.*;

public final class GetNodeTreeJsonTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public GetNodeTreeJsonTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "获取一个或多个节点及其子节点的 JSON 树数据。单次使用 rootPath/nodePath；批量使用 nodes 数组。", objectSchema(
                Map.of(
                        "rootPath", stringSchema(),
                        "nodePath", stringSchema(),
                        "autoParse", booleanSchema(),
                        "maxDepth", numberSchema(),
                        "nodes", arraySchema(nodeReferenceWithReadOptionsSchema())
                ),
                List.of()
        ));
        this.service = service;
    }

    @Override
    public String name() {
        return "get_node_tree_json";
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        var nodes = ToolParamHelper.getObjectList(params, "nodes");
        if (params.containsKey("nodes")) {
            boolean defaultAutoParse = ToolParamHelper.getBoolean(params, "autoParse", true);
            int defaultMaxDepth = ToolParamHelper.getInt(params, "maxDepth", 0);
            var results = new ArrayList<Map<String, Object>>(nodes.size());
            for (Map<String, Object> node : nodes) {
                var reference = ToolParamHelper.getNodeReference(node);
                boolean autoParse = ToolParamHelper.getBoolean(node, "autoParse", defaultAutoParse);
                int maxDepth = ToolParamHelper.getInt(node, "maxDepth", defaultMaxDepth);
                results.add(Map.of(
                        "rootPath", reference.rootPath(),
                        "nodePath", reference.nodePath(),
                        "tree", service.getNodeTreeJson(session, reference, autoParse, maxDepth)
                ));
            }
            return Map.of("results", results);
        }

        boolean autoParse = ToolParamHelper.getBoolean(params, "autoParse", true);
        int maxDepth = ToolParamHelper.getInt(params, "maxDepth", 0);
        return Map.of("tree", service.getNodeTreeJson(session, ToolParamHelper.getNodeReference(params), autoParse, maxDepth));
    }
}
