package com.example.backend_b.services;

import com.example.backend_b.common.Enums.EstadoAusencia;
import com.example.backend_b.common.Enums.TipoReporte;
import com.example.backend_b.common.Utils;
import com.example.backend_b.common.security.AuthContext;
import com.example.backend_b.entities.Ausencia;
import com.example.backend_b.entities.Marcacion;
import com.example.backend_b.infrastructure.DTOs.Response.ResumenAsistenciaResponse;
import com.example.backend_b.infrastructure.repositories.AusenciaRepository;
import com.example.backend_b.infrastructure.repositories.MarcacionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.LocalDate;
import java.time.YearMonth;
import java.time.ZoneId;

/** Resumen para el dashboard y reportes CSV del periodo. */
@Service
public class ReporteAsistenciaService {

    private final MarcacionRepository marcacionRepo;
    private final AusenciaRepository ausenciaRepo;
    private final Clock clock;
    private final ZoneId zona;

    public ReporteAsistenciaService(MarcacionRepository marcacionRepo, AusenciaRepository ausenciaRepo, Clock clock, ZoneId zona) {
        this.marcacionRepo = marcacionRepo;
        this.ausenciaRepo = ausenciaRepo;
        this.clock = clock;
        this.zona = zona;
    }

    public record Reporte(String nombreArchivo, byte[] csv) {}

    @Transactional(readOnly = true)
    public ResumenAsistenciaResponse resumen(AuthContext auth, LocalDate fecha) {
        auth.exigirRol(AuthContext.ADMIN_RRHH, AuthContext.GERENTE);
        LocalDate dia = fecha != null ? fecha : LocalDate.now(clock.withZone(zona));
        return new ResumenAsistenciaResponse(dia,
                ausenciaRepo.countByTenantIdAndEstado(auth.tenantId(), EstadoAusencia.PENDIENTE),
                marcacionRepo.countByTenantIdAndFecha(auth.tenantId(), dia),
                marcacionRepo.countByTenantIdAndFechaAndTardeTrue(auth.tenantId(), dia));
    }

    @Transactional(readOnly = true)
    public Reporte csv(AuthContext auth, String periodo, TipoReporte tipo) {
        auth.exigirRol(AuthContext.ADMIN_RRHH, AuthContext.GERENTE);
        YearMonth ym = Utils.periodo(periodo);
        TipoReporte t = tipo == null ? TipoReporte.MARCACIONES : tipo;
        StringBuilder csv = new StringBuilder("﻿"); // BOM: Excel lee bien las tildes
        if (t == TipoReporte.MARCACIONES) {
            csv.append("fecha,empleado_id,area,hora_entrada,hora_salida,horas,tardanza_minutos,origen\n");
            for (Marcacion m : marcacionRepo.findByTenantIdAndFechaBetweenOrderByFechaAscEmpleadoIdAsc(
                    auth.tenantId(), ym.atDay(1), ym.atEndOfMonth())) {
                fila(csv, m.getFecha(), m.getEmpleadoId(), m.getArea(), m.getHoraEntrada(), m.getHoraSalida(),
                        m.getHoras() == null ? null : m.getHoras().toPlainString(), m.getTardanzaMinutos(), m.getOrigen());
            }
        } else {
            csv.append("ausencia_id,empleado_id,nombre_empleado,tipo,desde,hasta,dias,estado,aprobador_id\n");
            for (Ausencia a : ausenciaRepo.findByTenantIdAndDesdeLessThanEqualAndHastaGreaterThanEqualOrderByDesdeAsc(
                    auth.tenantId(), ym.atEndOfMonth(), ym.atDay(1))) {
                fila(csv, a.getId(), a.getEmpleadoId(), a.getNombreEmpleado(), a.getTipo(), a.getDesde(), a.getHasta(),
                        a.getDias(), a.getEstado(), a.getAprobadorId());
            }
        }
        String nombre = t.name().toLowerCase() + "-" + auth.tenantId() + "-" + ym + ".csv";
        return new Reporte(nombre, csv.toString().getBytes(StandardCharsets.UTF_8));
    }

    private static void fila(StringBuilder csv, Object... celdas) {
        for (int i = 0; i < celdas.length; i++) {
            if (i > 0) csv.append(',');
            csv.append(celda(celdas[i]));
        }
        csv.append('\n');
    }

    /** Escapa comas/comillas y evita inyección de fórmulas al abrir en Excel. */
    static String celda(Object v) {
        if (v == null) return "";
        String s = v.toString();
        if (!s.isEmpty() && "=+-@".indexOf(s.charAt(0)) >= 0 && !s.matches("-?\\d+(\\.\\d+)?")) s = "'" + s;
        if (s.contains(",") || s.contains("\"") || s.contains("\n")) s = "\"" + s.replace("\"", "\"\"") + "\"";
        return s;
    }
}
