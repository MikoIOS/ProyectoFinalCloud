package com.example.backend_b.common.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Valida (y en desarrollo emite) JWT HS256. El secreto debe ser el mismo que usa ms-usuarios
 * para firmar: propiedad {@code hcm.jwt.secret} (variable de entorno JWT_SECRET).
 * Claims aceptados: tenant_id | tenantId | custom:tenant_id, user_id | sub, rol | role, empleado_id.
 */
@Component
public class JwtService {

    private static final Base64.Encoder ENC = Base64.getUrlEncoder().withoutPadding();
    private static final Base64.Decoder DEC = Base64.getUrlDecoder();

    private final String secreto;

    public JwtService(@Value("${hcm.jwt.secret}") String secreto) {
        this.secreto = secreto;
    }

    /** Devuelve la identidad si el token es válido; si no, lanza IllegalArgumentException. */
    public AuthContext validar(String token) {
        Map<String, Object> claims = verificar(token, Instant.now().getEpochSecond());
        String tenant = primero(claims, "tenant_id", "tenantId", "custom:tenant_id");
        if (tenant == null) throw new IllegalArgumentException("El token no tiene tenant_id");
        return new AuthContext(tenant,
                primero(claims, "user_id", "userId", "sub"),
                primero(claims, "rol", "role", "custom:rol"),
                primero(claims, "empleado_id", "empleadoId", "custom:empleado_id"));
    }

    public String emitir(AuthContext ctx, long segundosValidez) {
        Map<String, Object> claims = new LinkedHashMap<>();
        claims.put("tenant_id", ctx.tenantId());
        claims.put("user_id", ctx.userId());
        claims.put("rol", ctx.rol());
        if (ctx.empleadoId() != null) claims.put("empleado_id", ctx.empleadoId());
        claims.put("exp", Instant.now().getEpochSecond() + segundosValidez);
        String header = ENC.encodeToString("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
        String payload = ENC.encodeToString(MiniJson.write(claims).getBytes(StandardCharsets.UTF_8));
        return header + "." + payload + "." + ENC.encodeToString(hmac(header + "." + payload));
    }

    Map<String, Object> verificar(String token, long ahora) {
        if (token == null) throw new IllegalArgumentException("Token ausente");
        String[] partes = token.trim().split("\\.");
        if (partes.length != 3) throw new IllegalArgumentException("Token mal formado");
        Map<String, Object> header = MiniJson.parse(new String(DEC.decode(partes[0]), StandardCharsets.UTF_8));
        if (!"HS256".equals(header.get("alg"))) throw new IllegalArgumentException("Algoritmo no soportado");
        if (!MessageDigest.isEqual(hmac(partes[0] + "." + partes[1]), DEC.decode(partes[2]))) {
            throw new IllegalArgumentException("Firma inválida");
        }
        Map<String, Object> claims = MiniJson.parse(new String(DEC.decode(partes[1]), StandardCharsets.UTF_8));
        Object exp = claims.get("exp");
        if (exp instanceof Number n && n.longValue() < ahora) throw new IllegalArgumentException("Token expirado");
        return claims;
    }

    private byte[] hmac(String data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secreto.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String primero(Map<String, Object> claims, String... keys) {
        for (String k : keys) {
            Object v = claims.get(k);
            if (v != null && !v.toString().isBlank()) return v.toString().trim();
        }
        return null;
    }
}
