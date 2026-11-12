package com.example.backend_b.services;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Publica eventos de dominio en el formato común del grupo:
 * {"tipo_evento","tenant_id","origen","timestamp","datos"}.
 * <ol>
 *   <li>Dentro de la app: como evento de Spring (lo escucha {@link EventosInternosListener}; por ejemplo,
 *       AusenciaAprobada → descuento en nóminas).</li>
 *   <li>Hacia afuera: POST al webhook {@code hcm.eventos.webhook-url}, si está configurado
 *       (ahí se conecta SNS, una cola o ms-notificaciones al desplegar).</li>
 * </ol>
 */
@Service
public class EventoPublisher {

    private static final Logger log = LoggerFactory.getLogger(EventoPublisher.class);

    /** Evento tal como viaja entre microservicios. */
    public record EventoDominio(String tipoEvento, String tenantId, String origen, String timestamp, Map<String, Object> datos) {

        public Map<String, Object> comoMapa() {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("tipo_evento", tipoEvento);
            m.put("tenant_id", tenantId);
            m.put("origen", origen);
            m.put("timestamp", timestamp);
            m.put("datos", datos);
            return m;
        }
    }

    private final ApplicationEventPublisher springEvents;
    private final EventoWebhookSender webhook;
    private final Clock clock;

    public EventoPublisher(ApplicationEventPublisher springEvents, EventoWebhookSender webhook, Clock clock) {
        this.springEvents = springEvents;
        this.webhook = webhook;
        this.clock = clock;
    }

    public void publicar(String tipoEvento, String tenantId, String origen, Map<String, Object> datos) {
        EventoDominio e = new EventoDominio(tipoEvento, tenantId, origen, clock.instant().toString(), datos);
        log.info("Evento {} tenant={} origen={}", tipoEvento, tenantId, origen);
        springEvents.publishEvent(e);
        webhook.enviar(e);
    }
}
