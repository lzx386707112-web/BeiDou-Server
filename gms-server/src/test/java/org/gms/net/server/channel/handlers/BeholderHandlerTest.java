package org.gms.net.server.channel.handlers;

import org.gms.client.Character;
import org.gms.client.Client;
import org.gms.constants.skills.DarkKnight;
import org.gms.manager.ServerManager;
import org.gms.net.packet.InPacket;
import org.gms.server.maps.Summon;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;

import java.util.List;

import static org.mockito.Answers.RETURNS_MOCKS;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

class BeholderHandlerTest {

    @BeforeAll
    static void configureApplicationContext() {
        new ServerManager().setApplicationContext(mock(ApplicationContext.class, RETURNS_MOCKS));
    }

    @Test
    void staleSummonOidDoesNotMutateCharacterState() {
        Character player = mock(Character.class);
        Client client = mock(Client.class);
        InPacket packet = mock(InPacket.class);
        Summon summon = mock(Summon.class);
        when(client.getPlayer()).thenReturn(player);
        when(player.getSummonsValues()).thenReturn(List.of(summon));
        when(summon.getObjectId()).thenReturn(100);
        when(packet.readInt()).thenReturn(99);

        new BeholderHandler().handlePacket(packet, client);

        verify(player).getSummonsValues();
        verifyNoMoreInteractions(player);
        verify(packet).readInt();
        verifyNoMoreInteractions(packet);
    }

    @Test
    void matchingBeholderOidConsumesAuraPayload() {
        Character player = mock(Character.class);
        Client client = mock(Client.class);
        InPacket packet = mock(InPacket.class);
        Summon summon = mock(Summon.class);
        when(client.getPlayer()).thenReturn(player);
        when(player.getSummonsValues()).thenReturn(List.of(summon));
        when(summon.getObjectId()).thenReturn(100);
        when(packet.readInt()).thenReturn(100, DarkKnight.AURA_OF_BEHOLDER);

        new BeholderHandler().handlePacket(packet, client);

        verify(packet).readShort();
    }

    @Test
    void matchingBeholderOidConsumesHexPayload() {
        Character player = mock(Character.class);
        Client client = mock(Client.class);
        InPacket packet = mock(InPacket.class);
        Summon summon = mock(Summon.class);
        when(client.getPlayer()).thenReturn(player);
        when(player.getSummonsValues()).thenReturn(List.of(summon));
        when(summon.getObjectId()).thenReturn(100);
        when(packet.readInt()).thenReturn(100, DarkKnight.HEX_OF_BEHOLDER);

        new BeholderHandler().handlePacket(packet, client);

        verify(packet).readByte();
    }
}
