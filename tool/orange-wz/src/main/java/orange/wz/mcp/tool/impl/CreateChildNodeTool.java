package orange.wz.mcp.tool.impl;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.support.BaseSessionTool;
import orange.wz.mcp.tool.support.ToolParamHelper;

import java.util.List;
import java.util.Map;

import static orange.wz.mcp.tool.support.ToolSchemas.*;

public final class CreateChildNodeTool extends BaseSessionTool {
    private final McpWorkspaceService service;

    public CreateChildNodeTool(McpSessionManager sessionManager, McpWorkspaceService service) {
        super(sessionManager, "在指定父节点下创建子节点。", objectSchema(
                Map.ofEntries(
                        Map.entry("rootPath", stringSchema()),
                        Map.entry("nodePath", stringSchema()),
                        Map.entry("type", stringSchema()),
                        Map.entry("name", stringSchema()),
                        Map.entry("value", stringSchema()),
                        Map.entry("x", numberSchema()),
                        Map.entry("y", numberSchema()),
                        Map.entry("base64Png", stringSchema()),
                        Map.entry("base64Mp3", stringSchema()),
                        Map.entry("pngFormat", stringSchema()),
                        Map.entry("autoParse", booleanSchema())
                ),
                List.of("rootPath", "type", "name")
        ));
        this.service = service;
    }

    @Override
    public String name() {
        return "create_child_node";
    }

    @Override
    public Map<String, Object> invoke(Map<String, Object> params) {
        var session = session(params);
        var parent = ToolParamHelper.getNodeReference(params);
        String type = ToolParamHelper.requireString(params, "type");
        String nodeName = ToolParamHelper.requireString(params, "name");
        String value = ToolParamHelper.getString(params, "value", null);
        String base64Png = ToolParamHelper.getString(params, "base64Png", null);
        String base64Mp3 = ToolParamHelper.getString(params, "base64Mp3", null);
        String pngFormat = ToolParamHelper.getString(params, "pngFormat", null);
        boolean autoParse = ToolParamHelper.getBoolean(params, "autoParse", true);

        Integer x = params.get("x") instanceof Number n ? n.intValue() : null;
        Integer y = params.get("y") instanceof Number n ? n.intValue() : null;

        return Map.of(
                "node",
                service.createChildNode(
                        session,
                        parent,
                        type,
                        nodeName,
                        value,
                        x,
                        y,
                        base64Png,
                        base64Mp3,
                        pngFormat,
                        autoParse
                )
        );
    }
}
