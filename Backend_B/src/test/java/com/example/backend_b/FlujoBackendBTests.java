package com.example.backend_b;

import com.example.backend_b.common.Enums.EstadoAusencia;
import com.example.backend_b.common.Enums.EstadoPlanilla;
import com.example.backend_b.common.Enums.TipoAusencia;
import com.example.backend_b.common.Enums.TipoConcepto;
import com.example.backend_b.common.exception.AccesoDenegadoException;
import com.example.backend_b.common.exception.ConflictoException;
import com.example.backend_b.common.exception.ResourceNotFoundException;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.infrastructure.DTOs.Response.AusenciaResponse;
import com.example.backend_b.infrastructure.DTOs.Response.MarcacionResponse;
import com.example.backend_b.infrastructure.DTOs.Response.NominaResumenResponse;
import com.example.backend_b.infrastructure.DTOs.Response.PlanillaResponse;
import com.example.backend_b.infrastructure.DTOs.request.AusenciaRequest;
import com.example.backend_b.infrastructure.DTOs.request.CambiarEstadoAusenciaRequest;
import com.example.backend_b.infrastructure.DTOs.request.EventoRequest;
import com.example.backend_b.infrastructure.DTOs.request.GenerarPlanillaRequest;
import com.example.backend_b.infrastructure.DTOs.request.MarcacionRequest;
import com.example.backend_b.services.AusenciaService;
import com.example.backend_b.services.ConceptoNominaService;
import com.example.backend_b.services.EventoService;
import com.example.backend_b.services.MarcacionService;
import com.example.backend_b.services.NominaService;
import com.example.backend_b.services.PlanillaService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Flujo completo sobre H2: EmpleadoCreado → ausencia sin goce aprobada por el jefe → planilla del mes
 * con el descuento → aislamiento entre tenants.
 */
@SpringBootTest(properties = "hcm.seed.habilitado=false")
class FlujoBackendBTests {

    @Autowired private EventoService eventoService;
    @Autowired private AusenciaService ausenciaService;
    @Autowired private MarcacionService marcacionService;
    @Autowired private ConceptoNominaService conceptoService;
    @Autowired private PlanillaService planillaService;
    @Autowired private NominaService nominaService;

    private void empleadoCreado(String tenant, String id, String jefe, String salario) {
        EventoRequest e = new EventoRequest();
        e.setTipoEvento("EmpleadoCreado");
        e.setTenantId(tenant);
        e.setOrigen("ms-empleados");
        Map<String, Object> datos = new HashMap<>();
        datos.put("empleado_id", id);
        datos.put("nombres", "Empleado");
        datos.put("apellidos", id);
        datos.put("area", "Recursos Humanos");
        datos.put("cargo", "Analista");
        datos.put("jefe_id", jefe);
        datos.put("fecha_ingreso", "2023-03-15");
        datos.put("salario_base", salario);
        e.setDatos(datos);
        assertEquals("procesado", eventoService.recibir(e, null));
    }

    @Test
    void flujoCompleto() throws InterruptedException {
        String tenant = "t" + UUID.randomUUID().toString().substring(0, 8);
        AuthContext admin = new AuthContext(tenant, "usr-admin", AuthContext.ADMIN_RRHH, "emp-000002");
        AuthContext jefe = new AuthContext(tenant, "usr-jefe", AuthContext.GERENTE, "emp-000010");
        AuthContext emp = new AuthContext(tenant, "usr-45", AuthContext.EMPLEADO, "emp-000045");
        empleadoCreado(tenant, "emp-000010", null, "8000");
        empleadoCreado(tenant, "emp-000045", "emp-000010", "3000");

        // Marcación de entrada (autoservicio)
        MarcacionResponse m = marcacionService.marcar(emp, new MarcacionRequest());
        assertEquals("emp-000045", m.empleadoId());

        // Ausencia sin goce de 2 días en el mes actual, aprobada por el jefe
        YearMonth mes = YearMonth.now(ZoneId.of("America/Lima"));
        AusenciaRequest req = new AusenciaRequest();
        req.setTipo(TipoAusencia.SIN_GOCE);
        req.setDesde(mes.atDay(20));
        req.setHasta(mes.atDay(21));
        AusenciaResponse a = ausenciaService.solicitar(emp, req);
        assertEquals("emp-000010", a.aprobadorId());
        assertThrows(ConflictoException.class, () -> ausenciaService.solicitar(emp, req));

        CambiarEstadoAusenciaRequest aprobar = new CambiarEstadoAusenciaRequest();
        aprobar.setEstado(EstadoAusencia.APROBADA);
        assertThrows(AccesoDenegadoException.class, () -> ausenciaService.cambiarEstado(emp, a.id(), aprobar));
        assertEquals(EstadoAusencia.APROBADA, ausenciaService.cambiarEstado(jefe, a.id(), aprobar).estado());

        // Nóminas registró los días sin goce (evento AusenciaAprobada)
        assertTrue(conceptoService.listar(admin, mes.toString(), "emp-000045").stream()
                .anyMatch(c -> c.tipo() == TipoConcepto.SIN_GOCE && c.dias() == 2));

        // Planilla asíncrona del mes
        GenerarPlanillaRequest g = new GenerarPlanillaRequest();
        g.setPeriodo(mes.toString());
        assertEquals(EstadoPlanilla.EN_PROCESO, planillaService.generar(admin, g).estado());
        PlanillaResponse p = null;
        for (int i = 0; i < 100; i++) {
            p = planillaService.obtener(admin, mes.toString());
            if (p.estado() != EstadoPlanilla.EN_PROCESO) break;
            Thread.sleep(100);
        }
        assertEquals(EstadoPlanilla.GENERADA, p.estado());
        assertEquals(2, p.procesados());

        NominaResumenResponse n = nominaService.delEmpleado(emp, "emp-000045", 0, 10).nominas().items().get(0);
        // 3000 − 200 (2 días sin goce) − 13% ONP de 2800 (364)
        assertEquals(0, new BigDecimal("2436.00").compareTo(n.neto()));
        assertTrue(nominaService.boleta(emp, n.id()).pdf().length > 500);

        // Aislamiento: otro tenant no ve la nómina; otro empleado tampoco
        AuthContext otroTenant = new AuthContext("otro-" + tenant, "u", AuthContext.ADMIN_RRHH, "emp-000002");
        assertThrows(ResourceNotFoundException.class, () -> nominaService.detalle(otroTenant, n.id()));
        AuthContext otroEmp = new AuthContext(tenant, "u", AuthContext.EMPLEADO, "emp-000010");
        assertThrows(AccesoDenegadoException.class, () -> nominaService.detalle(otroEmp, n.id()));

        // Saldo de vacaciones
        assertEquals(30, ausenciaService.saldo(emp, "emp-000045").diasDisponibles());
        LocalDate hoy = LocalDate.now(ZoneId.of("America/Lima"));
        assertTrue(!hoy.isBefore(m.fecha()));
    }
}
