package com.example.backend_b.services;

import com.example.backend_b.common.exception.ResourceNotFoundException;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.entities.Empleado;
import com.example.backend_b.entities.Liquidacion;
import com.example.backend_b.infrastructure.DTOs.Response.LiquidacionResponse;
import com.example.backend_b.infrastructure.repositories.LiquidacionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;

import static com.example.backend_b.common.Utils.dinero;

/**
 * Liquidación referencial por cese (simplificada): vacaciones, CTS y gratificación truncas
 * en proporción a los meses completos desde el último corte. No reemplaza al cálculo legal;
 * el sueldo del mes de cese sale en la planilla de ese periodo.
 */
@Service
public class LiquidacionService {

    private final LiquidacionRepository repository;
    private final Clock clock;

    public LiquidacionService(LiquidacionRepository repository, Clock clock) {
        this.repository = repository;
        this.clock = clock;
    }

    @Transactional
    public Liquidacion registrar(Empleado e, LocalDate cese, String motivo) {
        Liquidacion l = repository.findByTenantIdAndEmpleadoId(e.getTenantId(), e.getEmpleadoId()).orElseGet(Liquidacion::new);
        if (!calcular(e, cese, motivo, l)) return null;
        l.setCalculadoEn(clock.instant());
        return repository.save(l);
    }

    @Transactional(readOnly = true)
    public LiquidacionResponse obtener(AuthContext auth, String empleadoId) {
        auth.exigirPropioOSupervisor(empleadoId, "Solo puedes ver tu propia liquidación");
        return repository.findByTenantIdAndEmpleadoId(auth.tenantId(), empleadoId).map(LiquidacionResponse::de)
                .orElseThrow(() -> new ResourceNotFoundException("No hay liquidación para el empleado " + empleadoId));
    }

    /** Llena la liquidación; false si el empleado no tiene salario. */
    static boolean calcular(Empleado e, LocalDate cese, String motivo, Liquidacion l) {
        BigDecimal salario = e.getSalarioBase();
        if (salario == null) return false;
        LocalDate ingreso = e.getFechaIngreso() != null ? e.getFechaIngreso() : cese.withDayOfYear(1);

        LocalDate aniversario = ingreso.withYear(cese.getYear());
        if (aniversario.isAfter(cese)) aniversario = aniversario.minusYears(1);
        if (aniversario.isBefore(ingreso)) aniversario = ingreso;
        long mesesVac = ChronoUnit.MONTHS.between(aniversario, cese);

        LocalDate corteCts = cese.getMonthValue() >= 11 ? LocalDate.of(cese.getYear(), 11, 1)
                : cese.getMonthValue() >= 5 ? LocalDate.of(cese.getYear(), 5, 1) : LocalDate.of(cese.getYear() - 1, 11, 1);
        if (corteCts.isBefore(ingreso)) corteCts = ingreso;
        long mesesCts = ChronoUnit.MONTHS.between(corteCts, cese);

        LocalDate corteGrati = cese.getMonthValue() >= 7 ? LocalDate.of(cese.getYear(), 7, 1) : LocalDate.of(cese.getYear(), 1, 1);
        if (corteGrati.isBefore(ingreso)) corteGrati = ingreso;
        long mesesGrati = ChronoUnit.MONTHS.between(corteGrati, cese);

        BigDecimal doceavo = salario.divide(BigDecimal.valueOf(12), 6, RoundingMode.HALF_UP);
        BigDecimal sexto = salario.divide(BigDecimal.valueOf(6), 6, RoundingMode.HALF_UP);
        BigDecimal vac = dinero(doceavo.multiply(BigDecimal.valueOf(mesesVac)));
        BigDecimal cts = dinero(doceavo.multiply(BigDecimal.valueOf(mesesCts)));
        BigDecimal grati = dinero(sexto.multiply(BigDecimal.valueOf(mesesGrati)));

        l.setTenantId(e.getTenantId());
        l.setEmpleadoId(e.getEmpleadoId());
        l.setFechaCese(cese);
        l.setMotivo(motivo);
        l.setVacacionesTruncas(vac);
        l.setCtsTrunca(cts);
        l.setGratificacionTrunca(grati);
        l.setTotal(dinero(vac.add(cts).add(grati)));
        return true;
    }
}
