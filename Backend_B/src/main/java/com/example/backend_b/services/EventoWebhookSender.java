package com.example.backend_b.services;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

/**
 * Envía los eventos a un webhook externo (opcional). Si {@code hcm.eventos.webhook-url} está vacío
 * no hace nada. Corre en segundo plano para no demorar la respuesta al usuario.
 */
@Service
public class EventoWebhookSender {

    private static final Logger log = LoggerFactory.getLogger(EventoWebhookSender.class);

    private final String url;
    private final String apiKey;
    private final RestClient http;

    public EventoWebhookSender(@Value("${hcm.eventos.webhook-url:}") String url,
                               @Value("${hcm.eventos.webhook-api-key:}") String apiKey) {
        this.url = url == null ? "" : url.trim();
        this.apiKey = apiKey == null ? "" : apiKey.trim();
        this.http = RestClient.create();
    }

    @Async("eventosExecutor")
    public void enviar(EventoPublisher.EventoDominio evento) {
        if (url.isEmpty()) return;
        try {
            http.post().uri(url)
                    .contentType(MediaType.APPLICATION_JSON)
                    .header("X-Api-Key", apiKey)
                    .body(evento.comoMapa())
                    .retrieve()
                    .toBodilessEntity();
        } catch (RuntimeException e) {
            log.warn("No se pudo enviar el evento {} al webhook: {}", evento.tipoEvento(), e.getMessage());
        }
    }
}
