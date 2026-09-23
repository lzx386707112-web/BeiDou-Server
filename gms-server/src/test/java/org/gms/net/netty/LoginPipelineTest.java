package org.gms.net.netty;

import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.nio.NioSocketChannel;
import io.netty.util.concurrent.DefaultEventExecutorGroup;
import org.gms.client.Client;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.Mockito.mock;

class LoginPipelineTest {

    @Test
    void clientPacketHandlerRunsOutsideTheNetworkEventLoop() {
        DefaultEventExecutorGroup packetExecutor = new DefaultEventExecutorGroup(1);
        NioEventLoopGroup networkExecutor = new NioEventLoopGroup(1);
        NioSocketChannel channel = new NioSocketChannel();
        try {
            networkExecutor.register(channel).syncUninterruptibly();
            new TestInitializer().initialize(channel, mock(Client.class), packetExecutor);

            ChannelHandlerContext clientContext = channel.pipeline().context("Client");
            assertSame(packetExecutor, clientContext.executor().parent());
        } finally {
            channel.close().syncUninterruptibly();
            packetExecutor.shutdownGracefully().syncUninterruptibly();
            networkExecutor.shutdownGracefully().syncUninterruptibly();
        }
    }

    private static final class TestInitializer extends ServerChannelInitializer {
        @Override
        protected void initChannel(io.netty.channel.socket.SocketChannel channel) {
        }

        void initialize(NioSocketChannel channel, Client client, DefaultEventExecutorGroup packetExecutor) {
            initPipeline(channel, client, packetExecutor);
        }
    }
}
