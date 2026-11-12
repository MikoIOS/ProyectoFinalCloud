package com.example.backend_b.entities;

import com.example.backend_b.common.Enums.EstadoAusencia;
import com.example.backend_b.common.Enums.TipoAusencia;
import jakarta.persistence.*;
import java.time.Instant;
import java.time.LocalDate;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Solicitud de vacaciones, permiso, licencia o ausencia sin goce, con aprobación del jefe (FASE1 §4.4). */
@Entity
@Table(name = "ausencias",
        indexes = {@Index(name = "ix_ausencias_tenant_empleado", columnList = "tenant_id, empleado_id"), @Index(name = "ix_ausencias_tenant_estado_aprobador", columnList = "tenant_id, estado, aprobador_id")})
@Getter
@Setter
@NoArgsConstructor
public class Ausencia {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "ausencias_seq")
    @SequenceGenerator(name = "ausencias_seq", sequenceName = "ausencias_seq", allocationSize = 50)
    private Long id;

    @Column(name = "tenant_id", nullable = false, length = 40)
    private String tenantId;

    @Column(name = "empleado_id", nullable = false, length = 40)
    private String empleadoId;

    @Column(length = 200)
    private String nombreEmpleado;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private TipoAusencia tipo;

    private Boolean conGoce;

    @Column(nullable = false)
    private LocalDate desde;

    @Column(nullable = false)
    private LocalDate hasta;

    private Integer dias;

    @Column(length = 300)
    private String motivo;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private EstadoAusencia estado;

    @Column(name = "aprobador_id", length = 40)
    private String aprobadorId;

    @Column(length = 60)
    private String solicitadoPor;

    private Instant solicitadoEn;

    @Column(length = 60)
    private String resueltoPor;

    @Column(length = 40)
    private String resueltoPorEmpleado;

    private Instant resueltoEn;

    @Column(length = 300)
    private String comentario;

    @Version
    private Long version;
}
