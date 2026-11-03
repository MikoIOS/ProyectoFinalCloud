package com.example.backend_b.entities;

import com.example.backend_b.common.Enums.TipoLineaNomina;
import jakarta.persistence.*;
import java.math.BigDecimal;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Línea de la boleta: ingreso, descuento o aporte del empleador. */
@Entity
@Table(name = "nomina_detalles")
@Getter
@Setter
@NoArgsConstructor
public class NominaDetalle {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "nomina_detalles_seq")
    @SequenceGenerator(name = "nomina_detalles_seq", sequenceName = "nomina_detalles_seq", allocationSize = 50)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "nomina_id")
    private Nomina nomina;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private TipoLineaNomina tipo;

    @Column(length = 120)
    private String concepto;

    @Column(precision = 12, scale = 2)
    private BigDecimal monto;

    private Integer orden;
}
