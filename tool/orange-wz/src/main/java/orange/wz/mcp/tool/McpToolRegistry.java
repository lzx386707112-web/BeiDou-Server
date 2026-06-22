package orange.wz.mcp.tool;

import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class McpToolRegistry {
    private final Map<String, McpTool> tools = new LinkedHashMap<>();

    public synchronized void register(McpTool tool) {
        tools.put(tool.name(), tool);
    }

    public synchronized McpTool get(String name) {
        return tools.get(name);
    }

    public synchronized Collection<McpTool> all() {
        return List.copyOf(tools.values());
    }
}
