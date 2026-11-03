package com.example.backend_b.infrastructure.DTOs.Response;

import java.util.List;
import java.util.function.Function;
import org.springframework.data.domain.Page;

/** Página de resultados (page empieza en 0). */
public record PaginaResponse<T>(
        List<T> items,
        int pagina,
        int tamano,
        long totalElementos,
        int totalPaginas) {

    public static <E, T> PaginaResponse<T> de(Page<E> page, Function<E, T> mapper) {
        return new PaginaResponse<>(page.getContent().stream().map(mapper).toList(),
                page.getNumber(), page.getSize(), page.getTotalElements(), page.getTotalPages());
    }

    public static <T> PaginaResponse<T> deLista(List<T> todos, int pagina, int tamano) {
        int desde = Math.min(todos.size(), pagina * tamano);
        int hasta = Math.min(todos.size(), desde + tamano);
        int paginas = tamano == 0 ? 0 : (todos.size() + tamano - 1) / tamano;
        return new PaginaResponse<>(todos.subList(desde, hasta), pagina, tamano, todos.size(), paginas);
    }
}
