package org.gms.client;

import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.gms.server.StatEffect;
import org.gms.server.maps.Summon;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.util.Collection;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class CharacterSummonStateTest {

    @BeforeAll
    static void configureApplicationContext() {
        ApplicationContext context = mock(ApplicationContext.class);
        ServiceProperty serviceProperty = new ServiceProperty();
        serviceProperty.setLanguage("zh-CN");
        MessageSource messageSource = mock(MessageSource.class);
        when(messageSource.getMessage(anyString(), any(Object[].class), any(Locale.class)))
                .thenReturn("");
        when(context.getBean(ServiceProperty.class)).thenReturn(serviceProperty);
        when(context.getBean(anyString(), eq(MessageSource.class))).thenReturn(messageSource);
        new ServerManager().setApplicationContext(context);
    }

    @Test
    void summonSnapshotCannotMutateCharacterState() throws Exception {
        Character character = newCharacter();
        Summon summon = mock(Summon.class);
        character.addSummon(100, summon);

        Collection<Summon> snapshot = character.getSummonsValues();
        snapshot.clear();

        assertSame(summon, character.getSummonByKey(100));
    }

    @Test
    void activeSummonIsResolvedFromTheBuffSource() throws Exception {
        Character character = newCharacter();
        StatEffect effect = mock(StatEffect.class);
        Summon matchingSummon = mock(Summon.class);
        Summon unrelatedSummon = mock(Summon.class);
        when(effect.getSourceId()).thenReturn(100);
        putEffect(character, BuffStat.SUMMON, effect);
        character.addSummon(100, matchingSummon);
        character.addSummon(200, unrelatedSummon);

        AtomicReference<Summon> resolved = new AtomicReference<>();
        character.withSummonForBuff(BuffStat.SUMMON, resolved::set);

        assertSame(matchingSummon, resolved.get());
    }

    @Test
    void missingSummonDoesNotResolveAnUnrelatedObject() throws Exception {
        Character character = newCharacter();
        StatEffect effect = mock(StatEffect.class);
        when(effect.getSourceId()).thenReturn(100);
        putEffect(character, BuffStat.SUMMON, effect);
        character.addSummon(200, mock(Summon.class));

        AtomicReference<Summon> resolved = new AtomicReference<>();
        character.withSummonForBuff(BuffStat.SUMMON, resolved::set);

        assertNull(resolved.get());
    }

    private static Character newCharacter() throws Exception {
        Constructor<Character> constructor = Character.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        return constructor.newInstance();
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    private static void putEffect(Character character, BuffStat stat, StatEffect effect)
            throws Exception {
        Class<?> holderClass = Class.forName("org.gms.client.Character$BuffStatValueHolder");
        Constructor<?> holderConstructor = holderClass.getDeclaredConstructor(
                StatEffect.class, long.class, int.class
        );
        holderConstructor.setAccessible(true);
        Object holder = holderConstructor.newInstance(effect, 0L, 1);

        Field effectsField = Character.class.getDeclaredField("effects");
        effectsField.setAccessible(true);
        ((Map) effectsField.get(character)).put(stat, holder);
    }
}
