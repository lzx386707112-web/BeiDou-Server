package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;

import java.util.List;
import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.*;

public final class BatchFindNodesTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public BatchFindNodesTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "兼容批量查询入口；新调用优先使用 query_nodes 的 queries 数组。", objectSchema(
                Map.of("queries", arraySchema(queryOperationSchema())),
                List.of("queries")
        ));
        this.service = service;
    }

    @Override
    public String name() {
        return "batch_find_nodes";
    }

    @SuppressWarnings("unchecked")
    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        Object queries = params.get("queries");
        List<Map<String, Object>> list = queries instanceof List<?> raw ? (List<Map<String, Object>>) raw : List.of();
        return Map.of("results", service.batchFindNodes(session, list));
    }
}
