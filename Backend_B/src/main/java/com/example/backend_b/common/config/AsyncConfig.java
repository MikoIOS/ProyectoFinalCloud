package com.example.backend_b.common.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;

/** Hilos para generar planillas en segundo plano y para enviar eventos al webhook. */
@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean(name = "planillaExecutor")
    public Executor planillaExecutor() {
        ThreadPoolTaskExecutor ex = new ThreadPoolTaskExecutor();
        ex.setCorePoolSize(2);
        ex.setMaxPoolSize(4);
        ex.setQueueCapacity(50);
        ex.setThreadNamePrefix("planilla-");
        ex.initialize();
        return ex;
    }

    @Bean(name = "eventosExecutor")
    public Executor eventosExecutor() {
        ThreadPoolTaskExecutor ex = new ThreadPoolTaskExecutor();
        ex.setCorePoolSize(1);
        ex.setMaxPoolSize(2);
        ex.setQueueCapacity(20000);
        ex.setThreadNamePrefix("eventos-");
        ex.initialize();
        return ex;
    }
}
