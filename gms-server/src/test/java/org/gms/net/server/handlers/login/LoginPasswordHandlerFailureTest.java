package org.gms.net.server.handlers.login;

import org.gms.client.Client;
import org.gms.net.packet.InPacket;
import org.gms.net.packet.Packet;
import org.gms.util.PacketCreator;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class LoginPasswordHandlerFailureTest {

    @Test
    void databaseFailureRespondsWithoutRunningMoreDatabaseChecks() {
        InPacket packet = mock(InPacket.class);
        Client client = mock(Client.class);
        when(client.getRemoteAddress()).thenReturn("127.0.0.1");
        when(packet.readString()).thenReturn("test", "password");
        when(packet.readBytes(4)).thenReturn(new byte[4]);
        when(client.login(anyString(), anyString(), any())).thenReturn(6);

        new LoginPasswordHandler().handlePacket(packet, client);

        ArgumentCaptor<Packet> response = ArgumentCaptor.forClass(Packet.class);
        verify(client).sendPacket(response.capture());
        assertArrayEquals(PacketCreator.getLoginFailed(6).getBytes(), response.getValue().getBytes());
        verify(client, never()).hasBannedIP();
        verify(client, never()).hasBannedMac();
        verify(client, never()).getTempBanCalendarFromDB();
    }
}
