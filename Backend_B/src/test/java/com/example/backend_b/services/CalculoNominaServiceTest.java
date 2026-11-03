package com.example.backend_b.services;

import com.example.backend_b.common.Enums.EstadoEmpleado;
import com.example.backend_b.common.Enums.TipoConcepto;
import com.example.backend_b.common.Enums.TipoLineaNomina;
import com.example.backend_b.entities.ConceptoNomina;
import com.example.backend_b.entities.Empleado;
import com.example.backend_b.entities.Liquidacion;
import com.example.backend_b.entities.Nomina;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Pruebas unitarias del cálculo de planilla y liquidación (sin Spring ni base de datos). */
class CalculoNominaServiceTest {

    private final CalculoNominaService calculo = new CalculoNominaService(new BigDecimal("0.13"), new BigDecimal("0.09"));

    private static Empleado empleado(String salario, LocalDate ingreso) {
        Empleado e = new Empleado();
        e.setTenantId("andina");
        e.setEmpleadoId("emp-000045");
        e.setNombres("María");
        e.setApellidos("Quispe");
        e.setSalarioBase(new BigDecimal(salario));
        e.setFechaIngreso(ingreso);
        e.setEstado(EstadoEmpleado.ACTIVO);
        return e;
    }

    private static ConceptoNomina concepto(TipoConcepto tipo, String monto, Integer dias) {
        ConceptoNomina c = new ConceptoNomina();
        c.setTipo(tipo);
        c.setConcepto(tipo.name());
        c.setMonto(monto == null ? null : new BigDecimal(monto));
        c.setDias(dias);
        return c;
    }

    @Test
    void ejemploDelDisenoFase1() {
        Nomina n = calculo.calcular(empleado("3500", LocalDate.of(2023, 3, 15)), YearMonth.of(2026, 10),
                List.of(concepto(TipoConcepto.BONO, "300", null)));
        assertEquals(new BigDecimal("3500.00"), n.getSueldoBase());
        assertEquals(new BigDecimal("300.00"), n.getBonos());
        assertEquals(new BigDecimal("455.00"), n.getDescuentos());
        assertEquals(new BigDecimal("3345.00"), n.getNeto());
        assertEquals(new BigDecimal("315.00"), n.getAporteEssalud());
        assertEquals("2026-10", n.getPeriodo());
        assertTrue(n.getDetalle().stream().anyMatch(d -> d.getTipo() == TipoLineaNomina.APORTE_EMPLEADOR));
    }

    @Test
    void sinGoceYDescuentoManual() {
        Nomina n = calculo.calcular(empleado("3000", LocalDate.of(2020, 1, 1)), YearMonth.of(2026, 11),
                List.of(concepto(TipoConcepto.SIN_GOCE, null, 2), concepto(TipoConcepto.DESCUENTO, "50", null)));
        // sin goce 200; ONP 13% de 2800 = 364; descuentos = 364 + 200 + 50
        assertEquals(new BigDecimal("614.00"), n.getDescuentos());
        assertEquals(new BigDecimal("2386.00"), n.getNeto());
    }

    @Test
    void ingresoAMitadDeMesEsProporcional() {
        Nomina n = calculo.calcular(empleado("2000", LocalDate.of(2026, 11, 16)), YearMonth.of(2026, 11), List.of());
        assertEquals(15, n.getDiasLaborados());
        assertEquals(new BigDecimal("1000.00"), n.getSueldoBase());
    }

    @Test
    void diasLaborados() {
        YearMonth nov = YearMonth.of(2026, 11);
        assertEquals(30, CalculoNominaService.diasLaborados(empleado("1", LocalDate.of(2020, 1, 1)), nov));
        assertEquals(0, CalculoNominaService.diasLaborados(empleado("1", LocalDate.of(2026, 12, 1)), nov));
        Empleado cesado = empleado("1", LocalDate.of(2020, 1, 1));
        cesado.setEstado(EstadoEmpleado.CESADO);
        cesado.setFechaCese(LocalDate.of(2026, 11, 10));
        assertEquals(10, CalculoNominaService.diasLaborados(cesado, nov));
        cesado.setFechaCese(LocalDate.of(2026, 10, 10));
        assertNull(calculo.calcular(cesado, nov, List.of()));
    }

    @Test
    void liquidacionPorCese() {
        Liquidacion l = new Liquidacion();
        assertTrue(LiquidacionService.calcular(empleado("3600", LocalDate.of(2024, 3, 1)), LocalDate.of(2026, 9, 30), "Renuncia", l));
        assertEquals(new BigDecimal("1800.00"), l.getVacacionesTruncas()); // 6 meses × 3600/12
        assertEquals(new BigDecimal("1200.00"), l.getCtsTrunca());         // 4 meses desde mayo
        assertEquals(new BigDecimal("1200.00"), l.getGratificacionTrunca()); // 2 meses desde julio × 3600/6
        assertEquals(new BigDecimal("4200.00"), l.getTotal());
    }
}
