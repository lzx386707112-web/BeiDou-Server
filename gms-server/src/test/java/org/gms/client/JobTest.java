package org.gms.client;

import org.gms.manager.ServerManager;
import org.gms.property.ServiceProperty;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.context.ApplicationContext;
import org.springframework.context.MessageSource;

import java.util.Locale;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class JobTest {

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
    void cygnusFourthJobsRemainFourthJobAtRebirthLevel() {
        assertEquals(Job.DAWNWARRIOR3, Job.changeJobByLevel(Job.DAWNWARRIOR4, 119));
        assertEquals(Job.BLAZEWIZARD3, Job.changeJobByLevel(Job.BLAZEWIZARD4, 119));
        assertEquals(Job.WINDARCHER3, Job.changeJobByLevel(Job.WINDARCHER4, 119));
        assertEquals(Job.NIGHTWALKER3, Job.changeJobByLevel(Job.NIGHTWALKER4, 119));
        assertEquals(Job.THUNDERBREAKER3, Job.changeJobByLevel(Job.THUNDERBREAKER4, 119));

        assertEquals(Job.DAWNWARRIOR4, Job.changeJobByLevel(Job.DAWNWARRIOR4, 120));
        assertEquals(Job.BLAZEWIZARD4, Job.changeJobByLevel(Job.BLAZEWIZARD4, 120));
        assertEquals(Job.WINDARCHER4, Job.changeJobByLevel(Job.WINDARCHER4, 120));
        assertEquals(Job.NIGHTWALKER4, Job.changeJobByLevel(Job.NIGHTWALKER4, 120));
        assertEquals(Job.THUNDERBREAKER4, Job.changeJobByLevel(Job.THUNDERBREAKER4, 120));
    }
}
