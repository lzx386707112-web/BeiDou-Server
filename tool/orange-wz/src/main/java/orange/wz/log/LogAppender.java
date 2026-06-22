package orange.wz.log;

import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.AppenderBase;

import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;

public class LogAppender extends AppenderBase<ILoggingEvent> {

    // 全局队列（Appender 线程写，Swing 线程读）
    public static final BlockingQueue<ILoggingEvent> QUEUE =
            new LinkedBlockingQueue<>(10_000);

    @Override
    protected void append(ILoggingEvent event) {
        // 队列满了就丢（防止 OOM）
        QUEUE.offer(event);
    }
}
