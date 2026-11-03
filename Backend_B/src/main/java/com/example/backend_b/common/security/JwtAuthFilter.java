package com.example.backend_b.common.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * Lee "Authorization: Bearer &lt;jwt&gt;", lo valida y deja la identidad ({@link AuthContext}) en el
 * SecurityContext. Si no hay token o es inválido, la petición sigue sin autenticar y
 * SecurityConfig responde 401 en las rutas protegidas.
 * No es @Component a propósito: se registra solo dentro de la cadena de Spring Security.
 */
public class JwtAuthFilter extends OncePerRequestFilter {

    private static final Logger log = LoggerFactory.getLogger(JwtAuthFilter.class);

    private final JwtService jwtService;

    public JwtAuthFilter(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String header = request.getHeader("Authorization");
        if (header != null && header.regionMatches(true, 0, "Bearer ", 0, 7)) {
            try {
                AuthContext ctx = jwtService.validar(header.substring(7));
                String rol = ctx.rol() == null ? "SIN_ROL" : ctx.rol().toUpperCase();
                UsernamePasswordAuthenticationToken auth = new UsernamePasswordAuthenticationToken(
                        ctx, null, List.of(new SimpleGrantedAuthority("ROLE_" + rol)));
                SecurityContextHolder.getContext().setAuthentication(auth);
            } catch (IllegalArgumentException e) {
                log.debug("JWT rechazado: {}", e.getMessage());
            }
        }
        chain.doFilter(request, response);
    }
}
