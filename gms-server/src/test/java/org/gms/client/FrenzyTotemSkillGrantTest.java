package org.gms.client;

import org.gms.constants.id.ItemId;
import org.gms.constants.skills.Beginner;
import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.lang.reflect.Field;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyByte;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doCallRealMethod;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.RETURNS_MOCKS;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class FrenzyTotemSkillGrantTest {
    private Map<Integer, Skill> previousSkills;
    private Skill frenzySkill;

    @BeforeAll
    static void configureApplicationContext() {
        ApplicationContext context = mock(ApplicationContext.class, RETURNS_MOCKS);
        ServiceProperty serviceProperty = new ServiceProperty();
        serviceProperty.setLanguage("zh-CN");
        MessageSource messageSource = mock(MessageSource.class);
        when(messageSource.getMessage(anyString(), any(Object[].class), any(Locale.class)))
                .thenReturn("");
        when(context.getBean(ServiceProperty.class)).thenReturn(serviceProperty);
        when(context.getBean(anyString(), eq(MessageSource.class))).thenReturn(messageSource);
        new ServerManager().setApplicationContext(context);
    }

    @BeforeEach
    @SuppressWarnings("unchecked")
    void installSkill() throws Exception {
        Field field = SkillFactory.class.getDeclaredField("skills");
        field.setAccessible(true);
        previousSkills = (Map<Integer, Skill>) field.get(null);
        frenzySkill = new Skill(Beginner.FRENZY_TOTEM);
        Map<Integer, Skill> skills = new HashMap<>(previousSkills);
        skills.put(Beginner.FRENZY_TOTEM, frenzySkill);
        field.set(null, skills);
    }

    @AfterEach
    void restoreSkills() throws Exception {
        Field field = SkillFactory.class.getDeclaredField("skills");
        field.setAccessible(true);
        field.set(null, previousSkills);
    }

    @Test
    void equippingTotemGrantsBeginnerSkill() {
        Character character = mock(Character.class);
        doCallRealMethod().when(character).equippedItem(ItemId.FRENZY_TOTEM);
        when(character.getSkillLevel(frenzySkill)).thenReturn((byte) 0);

        character.equippedItem(ItemId.FRENZY_TOTEM);

        verify(character).changeSkillLevel(frenzySkill, (byte) 1, 1, -1);
    }

    @Test
    void unequippingTotemKeepsBeginnerSkill() {
        Character character = mock(Character.class);
        doCallRealMethod().when(character).unequippedItem(ItemId.FRENZY_TOTEM);
        when(character.getSkillLevel(frenzySkill)).thenReturn((byte) 1);

        character.unequippedItem(ItemId.FRENZY_TOTEM);

        verify(character, never()).changeSkillLevel(eq(frenzySkill), anyByte(), anyInt(), anyLong());
    }
}
