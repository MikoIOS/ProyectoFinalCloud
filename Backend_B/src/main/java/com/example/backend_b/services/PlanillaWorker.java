package com.example.backend_b.services;

import com.example.backend_b.common.Enums.EstadoPlanilla;
import com.example.backend_b.common.Utils;
import com.example.backend_b.entities.ConceptoNomina;
import com.example.backend_b.entities.Empleado;
import com.example.backend_b.entities.Nomina;
import com.example.backend_b.entities.Planilla;
import com.example.backend_b.infrastructure.repositories.ConceptoNominaRepository;
import com.example.backend_b.infrastructure.repositories.EmpleadoRepository;
import com.example.backend_b.infrastructure.repositories.NominaDetalleRepository;
import com.example.backend_b.infrastructure.repositories.NominaRepository;
import com.example.backend_b.infrastructure.repositories.PlanillaRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Calcula la planilla en segundo plano y por lotes (cada lote en su propia transacción):
 * así 10,000 empleados no bloquean la petición ni una sola transacción gigante.
 * Al terminar cada lote suma los totales en la cabecera y publica NominaGenerada por empleado.
 */
@Service
public class PlanillaWorker {

    private static final Logger log = LoggerFactory.getLogger(PlanillaWorker.class);
    public static final String ORIGEN = "ms-nominas";

    private final PlanillaRepository planillaRepo;
    private final EmpleadoRepository empleadoRepo;
    private final ConceptoNominaRepository conceptoRepo;
    private final NominaRepository nominaRepo;
    private final NominaDetalleRepository detalleRepo;
    private final CalculoNominaService calculo;
    private final EventoPublisher eventos;
    private final TransactionTemplate tx;
    private final Clock clock;
    private final int tamanoLote;

    public PlanillaWorker(PlanillaRepository planillaRepo, EmpleadoRepository empleadoRepo,
                          ConceptoNominaRepository conceptoRepo, NominaRepository nominaRepo,
                          NominaDetalleRepository detalleRepo, CalculoNominaService calculo, EventoPublisher eventos,
                          PlatformTransactionManager txManager, Clock clock,
                          @Value("${hcm.nominas.tamano-lote:200}") int tamanoLote) {
        this.planillaRepo = planillaRepo;
        this.empleadoRepo = empleadoRepo;
        this.conceptoRepo = conceptoRepo;
        this.nominaRepo = nominaRepo;
        this.detalleRepo = detalleRepo;
        this.calculo = calculo;
        this.eventos = eventos;
        this.tx = new TransactionTemplate(txManager);
        this.clock = clock;
        this.tamanoLote = tamanoLote;
    }

    @Async("planillaExecutor")
    public void procesar(Long planillaId, String ejecucionId) {
        procesarAhora(planillaId, ejecucionId);
    }

    /** Versión síncrona (la usan los tests). */
    public void procesarAhora(Long planillaId, String ejecucionId) {
        Planilla cabecera = planillaRepo.findById(planillaId).orElse(null);
        if (cabecera == null || !ejecucionId.equals(cabecera.getEjecucionId())) return;
        String tenant = cabecera.getTenantId();
        String periodoTxt = cabecera.getPeriodo();
        YearMonth periodo = YearMonth.parse(periodoTxt);
        try {
            // Si se recalcula, se borran las nóminas anteriores del periodo
            tx.executeWithoutResult(s -> {
                detalleRepo.borrarPeriodo(tenant, periodoTxt);
                nominaRepo.borrarPeriodo(tenant, periodoTxt);
            });

            List<Empleado> empleados = new ArrayList<>();
            for (Empleado e : empleadoRepo.findByTenantIdOrderByEmpleadoIdAsc(tenant)) {
                if (e.getSalarioBase() != null && CalculoNominaService.diasLaborados(e, periodo) > 0) empleados.add(e);
            }
            Map<String, List<ConceptoNomina>> conceptos = new HashMap<>();
            for (ConceptoNomina c : conceptoRepo.findByTenantIdAndPeriodo(tenant, periodoTxt)) {
                conceptos.computeIfAbsent(c.getEmpleadoId(), k -> new ArrayList<>()).add(c);
            }
            actualizarCabecera(planillaId, ejecucionId, p -> p.setTotalEmpleados(empleados.size()));

            for (int i = 0; i < empleados.size(); i += tamanoLote) {
                List<Empleado> lote = empleados.subList(i, Math.min(empleados.size(), i + tamanoLote));
                List<Nomina> guardadas = tx.execute(s -> {
                    List<Nomina> nominas = new ArrayList<>();
                    for (Empleado e : lote) {
                        Nomina n = calculo.calcular(e, periodo, conceptos.getOrDefault(e.getEmpleadoId(), List.of()));
                        if (n == null) continue;
                        n.setGeneradoEn(clock.instant());
                        nominas.add(n);
                    }
                    return nominaRepo.saveAll(nominas);
                });
                if (!sumarLote(planillaId, ejecucionId, guardadas)) {
                    log.warn("Planilla {} {} reemplazada por otra ejecución; se detiene", tenant, periodoTxt);
                    return;
                }
                Map<String, String> emails = new HashMap<>();
                lote.forEach(e -> emails.put(e.getEmpleadoId(), e.getEmail()));
                for (Nomina n : guardadas) {
                    Map<String, Object> datos = new LinkedHashMap<>();
                    datos.put("nomina_id", n.getId());
                    datos.put("empleado_id", n.getEmpleadoId());
                    datos.put("email", emails.get(n.getEmpleadoId()));
                    datos.put("periodo", periodoTxt);
                    datos.put("neto", n.getNeto());
                    datos.put("mensaje", "Tu boleta de " + periodoTxt + " ya está disponible");
                    eventos.publicar("NominaGenerada", tenant, ORIGEN, datos);
                }
            }
            actualizarCabecera(planillaId, ejecucionId, p -> {
                p.setEstado(EstadoPlanilla.GENERADA);
                p.setCompletadoEn(clock.instant());
            });
            log.info("Planilla generada {} {}: {} empleados", tenant, periodoTxt, empleados.size());
        } catch (RuntimeException e) {
            log.error("Falló la planilla {} {}", tenant, periodoTxt, e);
            actualizarCabecera(planillaId, ejecucionId, p -> {
                p.setEstado(EstadoPlanilla.FALLIDA);
                p.setMensajeError(e.getClass().getSimpleName() + ": " + e.getMessage());
            });
        }
    }

    private boolean sumarLote(Long planillaId, String ejecucionId, List<Nomina> nominas) {
        BigDecimal bruto = BigDecimal.ZERO, desc = BigDecimal.ZERO, neto = BigDecimal.ZERO, essalud = BigDecimal.ZERO;
        for (Nomina n : nominas) {
            bruto = bruto.add(n.getSueldoBase()).add(n.getBonos());
            desc = desc.add(n.getDescuentos());
            neto = neto.add(n.getNeto());
            essalud = essalud.add(n.getAporteEssalud());
        }
        BigDecimal fb = bruto, fd = desc, fn = neto, fe = essalud;
        return actualizarCabecera(planillaId, ejecucionId, p -> {
            p.setProcesados(p.getProcesados() + nominas.size());
            p.setTotalBruto(Utils.dinero(p.getTotalBruto().add(fb)));
            p.setTotalDescuentos(Utils.dinero(p.getTotalDescuentos().add(fd)));
            p.setTotalNeto(Utils.dinero(p.getTotalNeto().add(fn)));
            p.setTotalEssalud(Utils.dinero(p.getTotalEssalud().add(fe)));
        });
    }

    /** Aplica el cambio solo si la cabecera sigue siendo de esta ejecución. */
    private boolean actualizarCabecera(Long planillaId, String ejecucionId, java.util.function.Consumer<Planilla> cambio) {
        Boolean ok = tx.execute(s -> {
            Planilla p = planillaRepo.findById(planillaId).orElse(null);
            if (p == null || !ejecucionId.equals(p.getEjecucionId())) return false;
            cambio.accept(p);
            planillaRepo.save(p);
            return true;
        });
        return Boolean.TRUE.equals(ok);
    }
}
