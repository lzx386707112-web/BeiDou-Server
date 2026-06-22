package orange.wz.mcp.http;

import com.fasterxml.jackson.annotation.JsonInclude;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record JsonRpcResponse(
        String jsonrpc,
        Object id,
        Object result,
        JsonRpcError error
) {
    public static JsonRpcResponse result(Object id, Object result) {
        return new JsonRpcResponse("2.0", id, result, null);
    }

    public static JsonRpcResponse error(Object id, int code, String message, Object data) {
        return new JsonRpcResponse("2.0", id, null, new JsonRpcError(code, message, data));
    }
}
