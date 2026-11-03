package com.example.backend_b.services;

import com.example.backend_b.common.Enums.EstadoEmpleado;
import com.example.backend_b.common.Enums.EstadoNomina;
import com.example.backend_b.common.Enums.TipoLineaNomina;
import com.example.backend_b.entities.ConceptoNomina;
import com.example.backend_b.entities.Empleado;
import com.example.backend_b.entities.Nomina;
import com.example.backend_b.entities.NominaDetalle;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.YearMonth;
import java.util.List;

import static com.example.backend_b.common.Utils.dinero;

/**
 * Cálculo de la boleta mensual (reglas simplificadas de planilla peruana):
 * <pre>
 *   sueldo_base = salario_mensual × días_laborados / 30          (mes comercial de 30 días)
 *   sin_goce    = salario_mensual / 30 × días sin goce aprobados
 *   pensión     = (sueldo_base − sin_goce) × TASA_PENSION        (ONP 13% por defecto)
 *   descuentos  = pensión + sin_goce + otros descuentos
 *   neto        = sueldo_base + bonos − descuentos                (nunca negativo)
 *   EsSalud 9%  = aporte del empleador, informativo
 * </pre>
 * Ejemplo de la Fase 1: 3500 + 300 de bono − 455 (13% ONP) = 3345.
 */
@Service
public class CalculoNominaService {

    private static final BigDecimal TREINTA = BigDecimal.valueOf(30);

    private final BigDecimal tasaPension;
    private final BigDecimal tasaEssalud;

    public CalculoNominaService(@Value("${hcm.nominas.tasa-pension:0.13}") BigDecimal tasaPension,
                                @Value("${hcm.nominas.tasa-essalud:0.09}") BigDecimal tasaEssalud) {
        this.tasaPension = tasaPension;
        this.tasaEssalud = tasaEssalud;
    }

    /** Días laborados en el periodo; 0 si el empleado no corresponde a esa planilla. */
    public static int diasLaborados(Empleado e, YearMonth periodo) {
        LocalDate inicioMes = periodo.atDay(1);
        LocalDate finMes = periodo.atEndOfMonth();
        LocalDate ingreso = e.getFechaIngreso();
        LocalDate cese = e.getFechaCese();
        if (e.getEstado() == EstadoEmpleado.CESADO && cese == null) return 0;
        LocalDate inicio = ingreso != null && ingreso.isAfter(inicioMes) ? ingreso : inicioMes;
        LocalDate fin = cese != null && cese.isBefore(finMes) ? cese : finMes;
        if (fin.isBefore(inicio)) return 0;
        if (inicio.equals(inicioMes) && fin.equals(finMes)) return 30;
        return Math.min(30, fin.getDayOfMonth() - inicio.getDayOfMonth() + 1);
    }

    /**
     * Arma la nómina (sin guardar). Devuelve null si el empleado no tiene salario o días en el periodo.
     *
     * @param conceptos bonos, descuentos y días sin goce de ese empleado en el periodo
     */
    public Nomina calcular(Empleado e, YearMonth periodo, List<ConceptoNomina> conceptos) {
        BigDecimal salario = e.getSalarioBase();
        int dias = diasLaborados(e, periodo);
        if (salario == null || salario.signum() <= 0 || dias <= 0) return null;

        BigDecimal valorDia = salario.divide(TREINTA, 6, RoundingMode.HALF_UP);
        BigDecimal sueldo = dinero(dias == 30 ? salario : valorDia.multiply(BigDecimal.valueOf(dias)));

        Nomina n = new Nomina();
        n.agregarLinea(linea(TipoLineaNomina.INGRESO, "Remuneración básica (" + dias + " días)", sueldo));

        BigDecimal bonos = BigDecimal.ZERO;
        BigDecimal otrosDescuentos = BigDecimal.ZERO;
        int diasSinGoce = 0;
        for (ConceptoNomina c : conceptos) {
            switch (c.getTipo()) {
                case BONO -> {
                    BigDecimal m = dinero(c.getMonto());
                    bonos = bonos.add(m);
                    n.agregarLinea(linea(TipoLineaNomina.INGRESO, c.getConcepto(), m));
                }
                case DESCUENTO -> {
                    BigDecimal m = dinero(c.getMonto());
                    otrosDescuentos = otrosDescuentos.add(m);
                    n.agregarLinea(linea(TipoLineaNomina.DESCUENTO, c.getConcepto(), m));
                }
                case SIN_GOCE -> diasSinGoce += c.getDias() == null ? 0 : c.getDias();
            }
        }
        diasSinGoce = Math.min(diasSinGoce, dias);
        BigDecimal sinGoce = dinero(valorDia.multiply(BigDecimal.valueOf(diasSinGoce)));
        if (sinGoce.compareTo(sueldo) > 0) sinGoce = sueldo;

        BigDecimal computable = sueldo.subtract(sinGoce);
        BigDecimal pension = dinero(computable.multiply(tasaPension));
        n.agregarLinea(linea(TipoLineaNomina.DESCUENTO, "Aporte pensión ONP (" + porcentaje(tasaPension) + ")", pension));
        if (diasSinGoce > 0) {
            n.agregarLinea(linea(TipoLineaNomina.DESCUENTO, "Ausencia sin goce (" + diasSinGoce + " días)", sinGoce));
        }
        BigDecimal essalud = dinero(computable.multiply(tasaEssalud));
        n.agregarLinea(linea(TipoLineaNomina.APORTE_EMPLEADOR, "EsSalud (" + porcentaje(tasaEssalud) + ")", essalud));

        BigDecimal totalDescuentos = dinero(pension.add(sinGoce).add(otrosDescuentos));
        BigDecimal neto = dinero(sueldo.add(bonos).subtract(totalDescuentos));
        if (neto.signum() < 0) neto = dinero(BigDecimal.ZERO);

        n.setTenantId(e.getTenantId());
        n.setPeriodo(periodo.toString());
        n.setEmpleadoId(e.getEmpleadoId());
        n.setNombreEmpleado(e.getNombreCompleto());
        n.setDocumento(e.getDocumento());
        n.setArea(e.getArea());
        n.setCargo(e.getCargo());
        n.setSalarioMensual(dinero(salario));
        n.setDiasLaborados(dias);
        n.setSueldoBase(sueldo);
        n.setBonos(dinero(bonos));
        n.setDescuentos(totalDescuentos);
        n.setNeto(neto);
        n.setAporteEssalud(essalud);
        n.setEstado(EstadoNomina.GENERADO);
        return n;
    }

    private static NominaDetalle linea(TipoLineaNomina tipo, String concepto, BigDecimal monto) {
        NominaDetalle d = new NominaDetalle();
        d.setTipo(tipo);
        d.setConcepto(concepto);
        d.setMonto(monto);
        return d;
    }

    private static String porcentaje(BigDecimal tasa) {
        return tasa.multiply(BigDecimal.valueOf(100)).stripTrailingZeros().toPlainString() + "%";
    }
}
