package orange.wz.mcp.server;

import orange.wz.mcp.service.McpWorkspaceService;
import orange.wz.mcp.service.impl.DefaultMcpWorkspaceService;
import orange.wz.mcp.session.McpSessionManager;
import orange.wz.mcp.tool.McpTool;
import orange.wz.mcp.tool.McpToolRegistry;
import orange.wz.mcp.tool.impl.*;
import orange.wz.mcp.support.McpException;
import org.springframework.stereotype.Component;

import java.util.Map;

@Component
public final class McpServerBootstrap {
    private final McpSessionManager sessionManager;
    private final McpWorkspaceService workspaceService;
    private final McpToolRegistry toolRegistry;

    public McpServerBootstrap() {
        this.sessionManager = new McpSessionManager();
        this.workspaceService = new DefaultMcpWorkspaceService();
        this.toolRegistry = new McpToolRegistry();
        registerBuiltInTools();
    }

    public McpSessionManager sessionManager() {
        return sessionManager;
    }

    public McpWorkspaceService workspaceService() {
        return workspaceService;
    }

    public McpToolRegistry toolRegistry() {
        return toolRegistry;
    }

    public Map<String, Object> invokeTool(String toolName, Map<String, Object> params) {
        McpTool tool = toolRegistry.get(toolName);
        if (tool == null) {
            throw new McpException("未知 tool: " + toolName);
        }
        return tool.invoke(params);
    }

    private void registerBuiltInTools() {
        toolRegistry.register(new LoadFilesTool(sessionManager, workspaceService));
        toolRegistry.register(new ListLoadedRootsTool(sessionManager, workspaceService));
        toolRegistry.register(new UnloadNodeTool(sessionManager, workspaceService));
        toolRegistry.register(new UnloadAllTool(sessionManager, workspaceService));
        toolRegistry.register(new CreateWzFileTool(sessionManager, workspaceService));
        toolRegistry.register(new CreateImgFileTool(sessionManager, workspaceService));
        toolRegistry.register(new ListChildrenTool(sessionManager, workspaceService));
        toolRegistry.register(new FindNodeTool(sessionManager, workspaceService));
        toolRegistry.register(new GetNodeDetailTool(sessionManager, workspaceService));
        toolRegistry.register(new GetNodeTreeJsonTool(sessionManager, workspaceService));
        toolRegistry.register(new SearchNodeTool(sessionManager, workspaceService));
        toolRegistry.register(new BatchFindNodesTool(sessionManager, workspaceService));
        toolRegistry.register(new QueryNodesTool(sessionManager, workspaceService));
        toolRegistry.register(new CreateChildNodeTool(sessionManager, workspaceService));
        toolRegistry.register(new DeleteNodeTool(sessionManager, workspaceService));
        toolRegistry.register(new CopyNodesTool(sessionManager, workspaceService));
        toolRegistry.register(new PasteNodesTool(sessionManager, workspaceService));
        toolRegistry.register(new BatchUpdateNodesTool(sessionManager, workspaceService));
        toolRegistry.register(new MutateNodesTool(sessionManager, workspaceService));
        toolRegistry.register(new SaveNodeTool(sessionManager, workspaceService));
        toolRegistry.register(new SaveNodeAsTool(sessionManager, workspaceService));
    }
}
