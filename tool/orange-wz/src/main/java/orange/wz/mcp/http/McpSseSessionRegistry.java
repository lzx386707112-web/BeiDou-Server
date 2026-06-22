package orange.wz.mcp.http;

import jakarta.annotation.PreDestroy;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

@Component
public final class McpSseSessionRegistry {
    private final Map<UUID, List<SseEmitter>> emitters = new ConcurrentHashMap<>();
    private final ScheduledExecutorService heartbeatExecutor = Executors.newSingleThreadScheduledExecutor();

    public McpSseSessionRegistry() {
        heartbeatExecutor.scheduleAtFixedRate(this::heartbeatAll, 15, 15, TimeUnit.SECONDS);
    }

    public SseEmitter open(UUID sessionId) {
        SseEmitter emitter = new SseEmitter(0L);
        emitters.computeIfAbsent(sessionId, ignored -> new CopyOnWriteArrayList<>()).add(emitter);

        emitter.onCompletion(() -> unregister(sessionId, emitter));
        emitter.onTimeout(() -> unregister(sessionId, emitter));
        emitter.onError(ex -> unregister(sessionId, emitter));

        try {
            emitter.send(SseEmitter.event().comment("mcp-stream-open"));
        } catch (IOException e) {
            unregister(sessionId, emitter);
            emitter.completeWithError(e);
        }
        return emitter;
    }

    public void close(UUID sessionId) {
        List<SseEmitter> sessionEmitters = emitters.remove(sessionId);
        if (sessionEmitters == null) {
            return;
        }
        for (SseEmitter emitter : sessionEmitters) {
            emitter.complete();
        }
    }

    private void unregister(UUID sessionId, SseEmitter emitter) {
        List<SseEmitter> sessionEmitters = emitters.get(sessionId);
        if (sessionEmitters == null) {
            return;
        }
        sessionEmitters.remove(emitter);
        if (sessionEmitters.isEmpty()) {
            emitters.remove(sessionId);
        }
    }

    private void heartbeatAll() {
        for (Map.Entry<UUID, List<SseEmitter>> entry : emitters.entrySet()) {
            for (SseEmitter emitter : entry.getValue()) {
                try {
                    emitter.send(SseEmitter.event().comment("keepalive"));
                } catch (IOException e) {
                    unregister(entry.getKey(), emitter);
                    emitter.completeWithError(e);
                }
            }
        }
    }

    @PreDestroy
    public void destroy() {
        heartbeatExecutor.shutdownNow();
        for (UUID sessionId : emitters.keySet()) {
            close(sessionId);
        }
    }
}
