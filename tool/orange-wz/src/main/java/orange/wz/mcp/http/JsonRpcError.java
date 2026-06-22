package orange.wz.mcp.http;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record JsonRpcError(
        int code,
        String message,
        Object data
) {
}
