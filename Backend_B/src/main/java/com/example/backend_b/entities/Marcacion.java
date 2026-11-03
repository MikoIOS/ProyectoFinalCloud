package com.example.backend_b.entities;

import com.example.backend_b.common.Enums.EstadoMarcacion;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalTime;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Marcación de entrada/salida de un empleado en un día (FASE1 §4.4). */
@Entity
@Table(name = "marcaciones",
        uniqueConstraints = {@UniqueConstraint(name = "uk_marcaciones_tenant_empleado_fecha", columnNames = {"tenant_id", "empleado_id", "fecha"})},
        indexes = {@Index(name = "ix_marcaciones_tenant_fecha", columnList = "tenant_id, fecha")})
@Getter
@Setter
@NoArgsConstructor
public class Marcacion {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "marcaciones_seq")
    @SequenceGenerator(name = "marcaciones_seq", sequenceName = "marcaciones_seq", allocationSize = 50)
    private Long id;

    @Column(name = "tenant_id", nullable = false, length = 40)
    private String tenantId;

    @Column(name = "empleado_id", nullable = false, length = 40)
    private String empleadoId;

    @Column(name = "fecha", nullable = false)
    private LocalDate fecha;

    private LocalTime horaEntrada;

    private LocalTime horaSalida;

    @Column(precision = 5, scale = 2)
    private BigDecimal horas;

    private Integer tardanzaMinutos;

    private Boolean tarde;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private EstadoMarcacion estado;

    @Column(length = 80)
    private String area;

    @Column(length = 20)
    private String origen;

    @Column(length = 60)
    private String registradoPor;

    @Version
    private Long version;
}
