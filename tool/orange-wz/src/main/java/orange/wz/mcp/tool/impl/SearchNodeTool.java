package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;
import orange.wz.mcp.tool.support.ToolParamHelper;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.*;

public final class SearchNodeTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public SearchNodeTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "按关键字搜索一个或多个节点范围。单次使用 rootPath/keyword；批量使用 queries 数组。searchIn=value 搜索节点值。", objectSchema(
                Map.of(
                        "rootPath", stringSchema(),
                        "nodePath", stringSchema(),
                        "keyword", stringSchema(),
                        "searchIn", stringSchema(),
                        "autoParse", booleanSchema(),
                        "queries", arraySchema(queryOperationSchema())
                ),
                List.of()
        ));
        this.service = service;
    }

    @Override
    public String name() {
        return "search_node";
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        var queries = ToolParamHelper.getObjectList(params, "queries");
        if (params.containsKey("queries")) {
            boolean defaultAutoParse = ToolParamHelper.getBoolean(params, "autoParse", true);
            String defaultSearchIn = String.valueOf(params.getOrDefault("searchIn", "name"));
            var results = new ArrayList<Map<String, Object>>(queries.size());
            for (Map<String, Object> query : queries) {
                var start = ToolParamHelper.getNodeReference(query);
                String keyword = ToolParamHelper.requireString(query, "keyword");
                boolean autoParse = ToolParamHelper.getBoolean(query, "autoParse", defaultAutoParse);
                String searchIn = String.valueOf(query.getOrDefault("searchIn", defaultSearchIn));
                results.add(search(session, start, keyword, searchIn, autoParse));
            }
            return Map.of("results", results);
        }

        var start = ToolParamHelper.getNodeReference(params);
        String keyword = ToolParamHelper.requireString(params, "keyword");
        boolean autoParse = ToolParamHelper.getBoolean(params, "autoParse", true);
        String searchIn = String.valueOf(params.getOrDefault("searchIn", "name"));
        return search(session, start, keyword, searchIn, autoParse);
    }

    private Map<String, Object> search(
            orange.wz.mcp.session.McpSessionState session,
            orange.wz.mcp.dto.NodeReference start,
            String keyword,
            String searchIn,
            boolean autoParse
    ) {
        Map<String, Object> result = new HashMap<>();
        result.put("rootPath", start.rootPath());
        result.put("nodePath", start.nodePath());
        result.put("keyword", keyword);
        if ("value".equalsIgnoreCase(searchIn)) {
            var matches = service.searchNodeByValue(session, start, keyword, autoParse);
            result.put("searchIn", "value");
            result.put("matches", matches);
            if (!matches.isEmpty()) {
                result.put("node", matches.get(0));
            }
            return result;
        }
        var matches = service.searchNodeByName(session, start, keyword, autoParse);
        result.put("searchIn", "name");
        result.put("matches", matches);
        if (!matches.isEmpty()) {
            result.put("node", matches.get(0));
        }
        return result;
    }
}
