package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;
import orange.wz.mcp.tool.support.ToolParamHelper;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.*;

public final class ListChildrenTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public ListChildrenTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "列出一个或多个节点的直接子节点。单次使用 rootPath/nodePath；批量使用 nodes 数组。", objectSchema(
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
        return "list_children";
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        var nodes = ToolParamHelper.getObjectList(params, "nodes");
        if (params.containsKey("nodes")) {
            boolean defaultAutoParse = ToolParamHelper.getBoolean(params, "autoParse", true);
            var results = new ArrayList<Map<String, Object>>(nodes.size());
            for (Map<String, Object> node : nodes) {
                var reference = ToolParamHelper.getNodeReference(node);
                boolean autoParse = ToolParamHelper.getBoolean(node, "autoParse", defaultAutoParse);
                results.add(Map.of(
                        "rootPath", reference.rootPath(),
                        "nodePath", reference.nodePath(),
                        "children", service.listChildren(session, reference, autoParse)
                ));
            }
            return Map.of("results", results);
        }

        boolean autoParse = ToolParamHelper.getBoolean(params, "autoParse", true);
        return Map.of("children", service.listChildren(session, ToolParamHelper.getNodeReference(params), autoParse));
    }
}
