package com.example.backend_b.common.security;

import java.math.BigDecimal;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Lector/escritor JSON mínimo para los claims del JWT (objeto plano con strings, números,
 * booleanos, null; arrays y objetos anidados se guardan como texto). Evita depender de la
 * versión de Jackson para algo tan pequeño.
 */
final class MiniJson {

    private final String s;
    private int i;

    private MiniJson(String s) {
        this.s = s;
    }

    static Map<String, Object> parse(String json) {
        MiniJson p = new MiniJson(json);
        p.ws();
        p.expect('{');
        Map<String, Object> out = new LinkedHashMap<>();
        p.ws();
        if (p.peek() == '}') return out;
        while (true) {
            p.ws();
            String key = p.string();
            p.ws();
            p.expect(':');
            p.ws();
            out.put(key, p.value());
            p.ws();
            char c = p.next();
            if (c == '}') return out;
            if (c != ',') throw new IllegalArgumentException("JSON inválido en el token");
        }
    }

    static String write(Map<String, Object> m) {
        StringBuilder b = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, Object> e : m.entrySet()) {
            if (!first) b.append(',');
            first = false;
            b.append(quote(e.getKey())).append(':');
            Object v = e.getValue();
            if (v == null) b.append("null");
            else if (v instanceof Number || v instanceof Boolean) b.append(v);
            else b.append(quote(v.toString()));
        }
        return b.append('}').toString();
    }

    private Object value() {
        char c = peek();
        if (c == '"') return string();
        if (c == '{' || c == '[') return raw();
        if (s.startsWith("true", i)) { i += 4; return Boolean.TRUE; }
        if (s.startsWith("false", i)) { i += 5; return Boolean.FALSE; }
        if (s.startsWith("null", i)) { i += 4; return null; }
        int start = i;
        while (i < s.length() && "+-0123456789.eE".indexOf(s.charAt(i)) >= 0) i++;
        if (start == i) throw new IllegalArgumentException("JSON inválido en el token");
        return new BigDecimal(s.substring(start, i));
    }

    /** Devuelve el texto de un objeto/array anidado sin interpretarlo. */
    private String raw() {
        int start = i, depth = 0;
        boolean inStr = false;
        while (i < s.length()) {
            char c = s.charAt(i++);
            if (inStr) {
                if (c == '\\') i++;
                else if (c == '"') inStr = false;
            } else if (c == '"') inStr = true;
            else if (c == '{' || c == '[') depth++;
            else if ((c == '}' || c == ']') && --depth == 0) return s.substring(start, i);
        }
        throw new IllegalArgumentException("JSON inválido en el token");
    }

    private String string() {
        expect('"');
        StringBuilder b = new StringBuilder();
        while (true) {
            char c = next();
            if (c == '"') return b.toString();
            if (c == '\\') {
                char e = next();
                switch (e) {
                    case 'n' -> b.append('\n');
                    case 't' -> b.append('\t');
                    case 'r' -> b.append('\r');
                    case 'b' -> b.append('\b');
                    case 'f' -> b.append('\f');
                    case 'u' -> {
                        b.append((char) Integer.parseInt(s.substring(i, i + 4), 16));
                        i += 4;
                    }
                    default -> b.append(e);
                }
            } else {
                b.append(c);
            }
        }
    }

    private static String quote(String v) {
        StringBuilder b = new StringBuilder("\"");
        for (char c : v.toCharArray()) {
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
            else b.append(c);
        }
        return b.append('"').toString();
    }

    private void ws() {
        while (i < s.length() && Character.isWhitespace(s.charAt(i))) i++;
    }

    private char peek() {
        if (i >= s.length()) throw new IllegalArgumentException("JSON inválido en el token");
        return s.charAt(i);
    }

    private char next() {
        char c = peek();
        i++;
        return c;
    }

    private void expect(char c) {
        if (next() != c) throw new IllegalArgumentException("JSON inválido en el token");
    }
}
