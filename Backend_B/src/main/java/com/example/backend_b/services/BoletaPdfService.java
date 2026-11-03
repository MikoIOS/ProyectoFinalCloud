package com.example.backend_b.services;

import com.example.backend_b.common.Enums.TipoLineaNomina;
import com.example.backend_b.common.pdf.SimplePdf;
import com.example.backend_b.entities.Nomina;
import com.example.backend_b.entities.NominaDetalle;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Dibuja la boleta de pago en PDF (A4) a partir de la nómina y su detalle. */
@Service
public class BoletaPdfService {

    private final Map<String, String> nombresTenant = new HashMap<>();

    public BoletaPdfService(@Value("${hcm.tenants.nombres:andina=Corporación Andina S.A.C.;pacifico=Pacífico Servicios S.A.;sierra=Sierra Industrial S.A.C.}") String nombres) {
        for (String par : nombres.split(";")) {
            String[] kv = par.split("=", 2);
            if (kv.length == 2) nombresTenant.put(kv[0].trim().toLowerCase(Locale.ROOT), kv[1].trim());
        }
    }

    public byte[] generar(Nomina n) {
        String empresa = nombresTenant.getOrDefault(n.getTenantId(), n.getTenantId());
        SimplePdf pdf = new SimplePdf();
        float izq = 50, der = SimplePdf.ANCHO - 50;
        float y = 790;

        pdf.fillRect(izq, y - 8, der - izq, 34, 0.86f);
        pdf.text(izq + 12, y + 4, 15, true, "BOLETA DE PAGO");
        pdf.textRight(der - 12, y + 4, 11, true, empresa.toUpperCase(Locale.ROOT));
        y -= 40;

        pdf.text(izq, y, 9, false, "Periodo: " + n.getPeriodo());
        pdf.textRight(der, y, 9, false, "N.º " + n.getPeriodo() + "-" + n.getEmpleadoId());
        y -= 26;

        y = fila(pdf, izq, y, "Trabajador", n.getNombreEmpleado());
        y = fila(pdf, izq, y, "Código", n.getEmpleadoId());
        y = fila(pdf, izq, y, "Documento", n.getDocumento());
        y = fila(pdf, izq, y, "Área / Cargo", nvl(n.getArea()) + " / " + nvl(n.getCargo()));
        y = fila(pdf, izq, y, "Días laborados", String.valueOf(n.getDiasLaborados()));
        y = fila(pdf, izq, y, "Remuneración mensual", "S/ " + fmt(n.getSalarioMensual()));
        y -= 10;

        y = seccion(pdf, izq, der, y, "INGRESOS", lineas(n, TipoLineaNomina.INGRESO));
        y = seccion(pdf, izq, der, y, "DESCUENTOS", lineas(n, TipoLineaNomina.DESCUENTO));
        y = seccion(pdf, izq, der, y, "APORTES DEL EMPLEADOR", lineas(n, TipoLineaNomina.APORTE_EMPLEADOR));

        y -= 6;
        pdf.line(izq, y, der, y, 0.8f);
        y -= 18;
        y = total(pdf, izq, der, y, "Total ingresos", n.getSueldoBase().add(n.getBonos()));
        y = total(pdf, izq, der, y, "Total descuentos", n.getDescuentos());
        pdf.fillRect(izq, y - 8, der - izq, 26, 0.9f);
        pdf.text(izq + 10, y, 12, true, "NETO A PAGAR");
        pdf.textRight(der - 10, y, 12, true, "S/ " + fmt(n.getNeto()));
        y -= 70;

        pdf.line(izq + 20, y, izq + 200, y, 0.5f);
        pdf.line(der - 200, y, der - 20, y, 0.5f);
        pdf.text(izq + 70, y - 14, 8, false, "Empleador");
        pdf.text(der - 135, y - 14, 8, false, "Trabajador");
        pdf.text(izq, 40, 7, false, "Documento generado por HCM SaaS · Backend B · " + (n.getGeneradoEn() == null ? "" : n.getGeneradoEn()));
        return pdf.build();
    }

    private static List<NominaDetalle> lineas(Nomina n, TipoLineaNomina tipo) {
        return n.getDetalle().stream().filter(d -> d.getTipo() == tipo).toList();
    }

    private static float fila(SimplePdf pdf, float izq, float y, String etiqueta, String valor) {
        pdf.text(izq, y, 9, true, etiqueta);
        pdf.text(izq + 140, y, 9, false, nvl(valor));
        return y - 15;
    }

    private static float seccion(SimplePdf pdf, float izq, float der, float y, String titulo, List<NominaDetalle> lineas) {
        if (lineas.isEmpty()) return y;
        pdf.fillRect(izq, y - 5, der - izq, 17, 0.93f);
        pdf.text(izq + 6, y, 9, true, titulo);
        pdf.textRight(der - 6, y, 9, true, "S/");
        y -= 18;
        for (NominaDetalle l : lineas) {
            pdf.text(izq + 10, y, 9, false, nvl(l.getConcepto()));
            pdf.textRight(der - 6, y, 9, false, fmt(l.getMonto()));
            y -= 14;
        }
        return y - 8;
    }

    private static float total(SimplePdf pdf, float izq, float der, float y, String etiqueta, BigDecimal v) {
        pdf.text(izq + 10, y, 10, true, etiqueta);
        pdf.textRight(der - 10, y, 10, false, "S/ " + fmt(v));
        return y - 22;
    }

    private static String nvl(String s) {
        return s == null || s.isBlank() ? "-" : s;
    }

    private static String fmt(BigDecimal v) {
        DecimalFormatSymbols s = new DecimalFormatSymbols(Locale.ROOT);
        s.setDecimalSeparator('.');
        s.setGroupingSeparator(',');
        return new DecimalFormat("#,##0.00", s).format(v == null ? BigDecimal.ZERO : v);
    }
}
