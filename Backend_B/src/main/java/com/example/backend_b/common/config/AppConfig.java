package com.example.backend_b.common.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.time.ZoneId;

@Configuration
public class AppConfig {

    /** Reloj de la aplicación (en los tests se reemplaza por uno fijo). */
    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }

    /** Zona horaria del negocio: fecha y hora de las marcaciones, "hoy" para solicitudes. */
    @Bean
    public ZoneId zonaNegocio(@Value("${hcm.zona-horaria:America/Lima}") String zona) {
        return ZoneId.of(zona);
    }
}
