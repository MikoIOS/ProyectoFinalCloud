package com.example.backend_b.common.pdf;

import java.io.ByteArrayOutputStream;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Generador de PDF de una página (A4) con texto, líneas y rectángulos, sin dependencias.
 * Usa las fuentes estándar Helvetica / Helvetica-Bold con WinAnsiEncoding (soporta tildes y ñ).
 * Suficiente para boletas y reportes; mantiene el jar del Lambda pequeño.
 */
public final class SimplePdf {

    public static final float ANCHO = 595f;
    public static final float ALTO = 842f;
    private static final Charset WIN_ANSI = Charset.forName("windows-1252");

    private final StringBuilder content = new StringBuilder();

    /** Texto con origen en (x, y) medido desde la esquina inferior izquierda. */
    public SimplePdf text(float x, float y, float size, boolean bold, String s) {
        content.append("BT /").append(bold ? "F2" : "F1").append(' ').append(fmt(size)).append(" Tf ")
                .append(fmt(x)).append(' ').append(fmt(y)).append(" Td (").append(escape(s)).append(") Tj ET\n");
        return this;
    }

    /** Texto alineado a la derecha terminando en x (aproximación con ancho medio de Helvetica). */
    public SimplePdf textRight(float xRight, float y, float size, boolean bold, String s) {
        return text(xRight - width(s, size, bold), y, size, bold, s);
    }

    public SimplePdf line(float x1, float y1, float x2, float y2, float grosor) {
        content.append(fmt(grosor)).append(" w ").append(fmt(x1)).append(' ').append(fmt(y1)).append(" m ")
                .append(fmt(x2)).append(' ').append(fmt(y2)).append(" l S\n");
        return this;
    }

    /** Rectángulo relleno con gris (0 = negro, 1 = blanco). */
    public SimplePdf fillRect(float x, float y, float w, float h, float gris) {
        content.append("q ").append(fmt(gris)).append(" g ").append(fmt(x)).append(' ').append(fmt(y)).append(' ')
                .append(fmt(w)).append(' ').append(fmt(h)).append(" re f Q\n");
        return this;
    }

    public static float width(String s, float size, boolean bold) {
        float total = 0;
        for (char c : s.toCharArray()) {
            if (c == ' ') total += 0.278f;
            else if (c == '.' || c == ',' || c == ':' || c == 'i' || c == 'l' || c == 'I') total += 0.28f;
            else if (Character.isDigit(c)) total += 0.556f;
            else if (Character.isUpperCase(c)) total += bold ? 0.72f : 0.667f;
            else total += bold ? 0.6f : 0.556f;
        }
        return total * size;
    }

    public byte[] build() {
        byte[] stream = content.toString().getBytes(WIN_ANSI);
        List<byte[]> objs = new ArrayList<>();
        objs.add(ascii("<< /Type /Catalog /Pages 2 0 R >>"));
        objs.add(ascii("<< /Type /Pages /Kids [3 0 R] /Count 1 >>"));
        objs.add(ascii("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 " + fmt(ANCHO) + " " + fmt(ALTO) + "] "
                + "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"));
        objs.add(ascii("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"));
        objs.add(ascii("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"));
        ByteArrayOutputStream s = new ByteArrayOutputStream();
        s.writeBytes(ascii("<< /Length " + stream.length + " >>\nstream\n"));
        s.writeBytes(stream);
        s.writeBytes(ascii("\nendstream"));
        objs.add(s.toByteArray());

        ByteArrayOutputStream out = new ByteArrayOutputStream();
        out.writeBytes(ascii("%PDF-1.4\n"));
        out.writeBytes(new byte[]{'%', (byte) 0xE2, (byte) 0xE3, (byte) 0xCF, (byte) 0xD3, '\n'});
        long[] offsets = new long[objs.size()];
        for (int i = 0; i < objs.size(); i++) {
            offsets[i] = out.size();
            out.writeBytes(ascii((i + 1) + " 0 obj\n"));
            out.writeBytes(objs.get(i));
            out.writeBytes(ascii("\nendobj\n"));
        }
        long xref = out.size();
        StringBuilder x = new StringBuilder("xref\n0 ").append(objs.size() + 1).append("\n0000000000 65535 f \n");
        for (long off : offsets) x.append(String.format(Locale.ROOT, "%010d 00000 n \n", off));
        x.append("trailer\n<< /Size ").append(objs.size() + 1).append(" /Root 1 0 R >>\nstartxref\n")
                .append(xref).append("\n%%EOF\n");
        out.writeBytes(ascii(x.toString()));
        return out.toByteArray();
    }

    private static String escape(String s) {
        StringBuilder b = new StringBuilder();
        for (char c : s.toCharArray()) {
            if (c == '(' || c == ')' || c == '\\') b.append('\\').append(c);
            else if (c < 32) b.append(' ');
            else if (WIN_ANSI.newEncoder().canEncode(c)) b.append(c);
            else b.append('?');
        }
        return b.toString();
    }

    private static String fmt(float f) {
        if (f == Math.rint(f)) return Integer.toString((int) f);
        return String.format(Locale.ROOT, "%.2f", f);
    }

    private static byte[] ascii(String s) {
        return s.getBytes(StandardCharsets.US_ASCII);
    }
}
