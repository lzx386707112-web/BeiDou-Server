package org.gms.server.life;

import org.gms.client.Job;
import org.gms.constants.game.GameConstants;
import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.gms.service.ConfigService;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.util.Locale;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class MonsterDropEntryTest {

    @BeforeAll
    static void configureApplicationContext() {
        ApplicationContext context = mock(ApplicationContext.class);
        ServiceProperty serviceProperty = new ServiceProperty();
        serviceProperty.setLanguage("zh-CN");
        MessageSource messageSource = mock(MessageSource.class);
        ConfigService configService = mock(ConfigService.class);
        when(messageSource.getMessage(anyString(), any(Object[].class), any(Locale.class)))
                .thenReturn("");
        when(context.getBean(ServiceProperty.class)).thenReturn(serviceProperty);
        when(context.getBean(ConfigService.class)).thenReturn(configService);
        when(context.getBean(anyString(), eq(MessageSource.class))).thenReturn(messageSource);
        when(configService.loadGameConfigs()).thenReturn(List.of());
        new ServerManager().setApplicationContext(context);
    }

    @Test
    void preservesUnsignedClientQuestIds() {
        MonsterDropEntry regular = new MonsterDropEntry(4034914, 500000, 1, 1, 34102);
        MonsterGlobalDropEntry global = new MonsterGlobalDropEntry(4034914, 500000, -1, 1, 1, 34584);

        assertEquals(34102, regular.questid);
        assertEquals(34584, global.questid);
    }

    @Test
    void fourthJobsCanReachLevel250() {
        assertEquals(250, GameConstants.getJobMaxLevel(Job.HERO));
        assertEquals(250, GameConstants.getJobMaxLevel(Job.DAWNWARRIOR4));
    }
}
