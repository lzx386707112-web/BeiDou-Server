package org.gms.net.netty;

import org.gms.client.Client;
import org.gms.constants.net.ServerConstants;
import io.netty.channel.Channel;
import io.netty.channel.ChannelHandler;
import io.netty.channel.ChannelInitializer;
import io.netty.channel.ChannelPipeline;
import io.netty.channel.socket.SocketChannel;
import io.netty.handler.timeout.IdleStateHandler;
import io.netty.util.concurrent.EventExecutorGroup;
import org.gms.net.encryption.ClientCyphers;
import org.gms.net.encryption.InitializationVector;
import org.gms.net.encryption.PacketCodec;
import org.gms.net.encryption.protocol.ProtocolFactory;
import org.gms.net.packet.logging.InPacketLogger;
import org.gms.net.packet.logging.OutPacketLogger;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.InetSocketAddress;
import java.util.concurrent.atomic.AtomicLong;

public abstract class ServerChannelInitializer extends ChannelInitializer<SocketChannel> {
    private static final Logger log = LoggerFactory.getLogger(ServerChannelInitializer.class);
    /** 无读写多久后触发空闲检测（原 30 秒，现 120 秒） */
    private static final int IDLE_TIME_SECONDS = 300;
    private static final ChannelHandler sendPacketLogger = new OutPacketLogger();
    private static final ChannelHandler receivePacketLogger = new InPacketLogger();

    static final AtomicLong sessionId = new AtomicLong(7777);

    String getRemoteAddress(Channel channel) {
        String remoteAddress = "null";
        try {
            remoteAddress = ((InetSocketAddress) channel.remoteAddress()).getAddress().getHostAddress();
        } catch (NullPointerException npe) {
            log.warn("Unable to get remote address from netty Channel: {}", channel, npe);
        }

        return remoteAddress;
    }

    void initPipeline(SocketChannel socketChannel, Client client) {
        initPipeline(socketChannel, client, null);
    }

    void initPipeline(SocketChannel socketChannel, Client client, EventExecutorGroup packetExecutor) {
        final InitializationVector sendIv = InitializationVector.generateSend();
        final InitializationVector recvIv = InitializationVector.generateReceive();
        final ProtocolFactory protocolFactory = new ProtocolFactory(ClientCyphers.of(sendIv, recvIv));
        protocolFactory.getProtocol(ServerConstants.VERSION).writeInitialUnencryptedHelloPacket(socketChannel, sendIv, recvIv, client);
        setUpHandlers(socketChannel.pipeline(), protocolFactory, client, packetExecutor);
    }

    private void setUpHandlers(ChannelPipeline pipeline, ProtocolFactory protocolFactory, Client client,
                               EventExecutorGroup packetExecutor) {
        pipeline.addLast("IdleStateHandler", new IdleStateHandler(0, 0, IDLE_TIME_SECONDS));
        pipeline.addLast("PacketCodec", new PacketCodec(protocolFactory));
        if (packetExecutor == null) {
            pipeline.addLast("Client", client);
        } else {
            pipeline.addLast(packetExecutor, "Client", client);
        }

        pipeline.addBefore("Client", "SendPacketLogger", sendPacketLogger);
        pipeline.addBefore("Client", "ReceivePacketLogger", receivePacketLogger);
    }
}
