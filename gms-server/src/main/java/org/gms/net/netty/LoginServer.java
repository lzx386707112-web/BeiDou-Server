package org.gms.net.netty;

import io.netty.bootstrap.ServerBootstrap;
import io.netty.channel.Channel;
import io.netty.channel.EventLoopGroup;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.nio.NioServerSocketChannel;
import io.netty.util.concurrent.DefaultEventExecutorGroup;
import io.netty.util.concurrent.DefaultThreadFactory;
import io.netty.util.concurrent.EventExecutorGroup;
import io.netty.util.concurrent.RejectedExecutionHandlers;

public class LoginServer extends AbstractServer {
    private static final int LOGIN_PACKET_THREADS = Math.max(2, Math.min(8, Runtime.getRuntime().availableProcessors()));
    private static final int MAX_PENDING_LOGIN_TASKS_PER_THREAD = 1024;
    public static final int WORLD_ID = -1;
    public static final int CHANNEL_ID = -1;
    private Channel channel;
    private EventLoopGroup parentGroup;
    private EventLoopGroup childGroup;
    private EventExecutorGroup packetExecutor;

    public LoginServer(int port) {
        super(port);
    }

    @Override
    public void start() {
        parentGroup = new NioEventLoopGroup();
        childGroup = new NioEventLoopGroup();
        packetExecutor = new DefaultEventExecutorGroup(
                LOGIN_PACKET_THREADS,
                new DefaultThreadFactory("login-packet"),
                MAX_PENDING_LOGIN_TASKS_PER_THREAD,
                RejectedExecutionHandlers.reject());
        ServerBootstrap bootstrap = new ServerBootstrap()
                .group(parentGroup, childGroup)
                .channel(NioServerSocketChannel.class)
                .childHandler(new LoginServerInitializer(packetExecutor));

        this.channel = bootstrap.bind(port).syncUninterruptibly().channel();
    }

    @Override
    public void stop() {
        if (channel == null) {
            throw new IllegalStateException("Must start LoginServer before stopping it");
        }

        channel.close().syncUninterruptibly();
        childGroup.shutdownGracefully().syncUninterruptibly();
        packetExecutor.shutdownGracefully().syncUninterruptibly();
        parentGroup.shutdownGracefully().syncUninterruptibly();
    }
}
