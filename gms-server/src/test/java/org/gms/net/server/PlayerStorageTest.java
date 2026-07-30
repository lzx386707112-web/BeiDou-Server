package org.gms.net.server;

import org.gms.client.Character;
import org.gms.manager.ServerManager;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Answers.RETURNS_MOCKS;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PlayerStorageTest {

    @BeforeAll
    static void configureApplicationContext() {
        new ServerManager().setApplicationContext(mock(ApplicationContext.class, RETURNS_MOCKS));
    }

    @Test
    void removesOnlyTheExpectedCharacterInstance() {
        PlayerStorage storage = new PlayerStorage();
        Character stored = character(1, "Stored");
        Character replacement = character(1, "Replacement");
        storage.addPlayer(stored);

        assertFalse(storage.removePlayer(replacement));
        assertSame(stored, storage.getCharacterById(1));

        assertTrue(storage.removePlayer(stored));
        assertNull(storage.getCharacterById(1));
        assertNull(storage.getCharacterByName("Stored"));
    }

    private static Character character(int id, String name) {
        Character character = mock(Character.class);
        when(character.getId()).thenReturn(id);
        when(character.getName()).thenReturn(name);
        return character;
    }
}
