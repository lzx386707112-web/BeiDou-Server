package orange.wz.mcp.dto;

import orange.wz.mcp.resolve.NodePathResolver;
import orange.wz.provider.WzObject;
import orange.wz.provider.tools.WzType;

public record NodeSummary(
        String name,
        String rootPath,
        String nodePath,
        WzType type
) {
    public static NodeSummary from(WzObject obj) {
        return new NodeSummary(
                obj.getName(),
                NodePathResolver.rootPathOf(obj),
                NodePathResolver.nodePathOf(obj),
                obj.getType()
        );
    }
}
