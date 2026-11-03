package com.example.backend_b.common;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.YearMonth;
import java.time.format.DateTimeParseException;
import java.util.regex.Pattern;

/** Utilidades pequeñas compartidas (montos y periodos AAAA-MM). */
public final class Utils {

    private static final Pattern PERIODO = Pattern.compile("^\\d{4}-(0[1-9]|1[0-2])$");

    private Utils() {}

    public static BigDecimal dinero(BigDecimal v) {
        return (v == null ? BigDecimal.ZERO : v).setScale(2, RoundingMode.HALF_UP);
    }

    public static BigDecimal cero() {
        return dinero(BigDecimal.ZERO);
    }

    /** Valida "AAAA-MM" y lo convierte; lanza IllegalArgumentException (→ 400) si no es válido. */
    public static YearMonth periodo(String periodo) {
        if (periodo == null || !PERIODO.matcher(periodo).matches()) {
            throw new IllegalArgumentException("Periodo inválido, use el formato AAAA-MM (ej. 2026-10)");
        }
        try {
            return YearMonth.parse(periodo);
        } catch (DateTimeParseException e) {
            throw new IllegalArgumentException("Periodo inválido, use el formato AAAA-MM (ej. 2026-10)");
        }
    }

    public static int tamanoPagina(Integer size) {
        if (size == null) return 50;
        if (size < 1) throw new IllegalArgumentException("'size' debe ser mayor a 0");
        return Math.min(size, 500);
    }

    public static int pagina(Integer page) {
        if (page == null) return 0;
        if (page < 0) throw new IllegalArgumentException("'page' no puede ser negativo");
        return page;
    }
}
