package orange.wz.mcp.session;

import orange.wz.provider.WzObject;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.locks.ReentrantLock;

public final class McpSessionState {
    private final UUID sessionId;
    private final List<WzObject> roots = new ArrayList<>();
    private final List<WzObject> clipboard = new ArrayList<>();
    private final ReentrantLock lock = new ReentrantLock();

    public McpSessionState(UUID sessionId) {
        this.sessionId = sessionId;
    }

    public UUID getSessionId() {
        return sessionId;
    }

    public List<WzObject> getRoots() {
        return roots;
    }

    public List<WzObject> getClipboard() {
        return clipboard;
    }

    public void lock() {
        lock.lock();
    }

    public void unlock() {
        lock.unlock();
    }
}
