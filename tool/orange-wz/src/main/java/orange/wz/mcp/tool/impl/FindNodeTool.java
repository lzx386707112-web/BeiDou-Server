package orange.wz.mcp.tool.impl;

import orange.wz.mcp.dto.NodeSummary;
import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;
import orange.wz.mcp.tool.support.ToolParamHelper;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.*;

public final class FindNodeTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public FindNodeTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "按路径查找一个或多个节点。单次使用 rootPath/nodePath；批量使用 nodes 数组。", objectSchema(
                Map.of(
                        "rootPath", stringSchema(),
                        "nodePath", stringSchema(),
                        "autoParse", booleanSchema(),
                        "nodes", arraySchema(nodeReferenceWithAutoParseSchema())
                ),
                List.of()
        ));
        this.service = service;
    }

    @Override
    public String name() {
        return "find_node";
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        var nodes = ToolParamHelper.getObjectList(params, "nodes");
        if (params.containsKey("nodes")) {
            boolean defaultAutoParse = ToolParamHelper.getBoolean(params, "autoParse", true);
            var results = new ArrayList<Map<String, Object>>(nodes.size());
            for (Map<String, Object> item : nodes) {
                var reference = ToolParamHelper.getNodeReference(item);
                boolean autoParse = ToolParamHelper.getBoolean(item, "autoParse", defaultAutoParse);
                var node = service.findNode(session, reference, autoParse);
                results.add(Map.of(
                        "rootPath", reference.rootPath(),
                        "nodePath", reference.nodePath(),
                        "node", NodeSummary.from(node)
                ));
            }
            return Map.of("results", results);
        }

        boolean autoParse = ToolParamHelper.getBoolean(params, "autoParse", true);
        var node = service.findNode(session, ToolParamHelper.getNodeReference(params), autoParse);
        return Map.of("node", NodeSummary.from(node));
    }
}
