package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.*;

public final class QueryNodesTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public QueryNodesTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "统一节点查询入口。直接传单项返回 result+results；传 queries 数组返回 results。支持路径、搜索、类型、详情、子节点和树查询。", objectSchema(
                Map.ofEntries(
                        Map.entry("queries", arraySchema(queryOperationSchema())),
                        Map.entry("op", stringSchema()),
                        Map.entry("rootPath", stringSchema()),
                        Map.entry("nodePath", stringSchema()),
                        Map.entry("keyword", stringSchema()),
                        Map.entry("searchIn", stringSchema()),
                        Map.entry("type", stringSchema()),
                        Map.entry("includeTree", booleanSchema()),
                        Map.entry("maxDepth", numberSchema()),
                        Map.entry("autoParse", booleanSchema())
                ),
                List.of()
        ));
        this.service = service;
    }

    @Override
    public String name() {
        return "query_nodes";
    }

    @SuppressWarnings("unchecked")
    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        Object queries = params.get("queries");
        List<Map<String, Object>> list;
        boolean batch = queries instanceof List<?>;
        if (queries instanceof List<?> raw) {
            list = (List<Map<String, Object>>) raw;
        } else {
            Map<String, Object> query = new HashMap<>(params);
            query.remove("sessionId");
            list = List.of(query);
        }
        var results = service.batchFindNodes(session, list);
        if (!batch && !results.isEmpty()) {
            return Map.of("result", results.get(0), "results", results);
        }
        return Map.of("results", results);
    }
}
