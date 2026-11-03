package com.example.backend_b.entities;

import com.example.backend_b.common.Enums.EstadoEmpleado;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Copia local del empleado (la fuente es ms-empleados; llega por POST /api/v1/eventos). La usan nóminas y asistencia. */
@Entity
@Table(name = "empleados",
        uniqueConstraints = {@UniqueConstraint(name = "uk_empleados_tenant_empleado", columnNames = {"tenant_id", "empleado_id"})},
        indexes = {@Index(name = "ix_empleados_tenant_jefe", columnList = "tenant_id, jefe_id")})
@Getter
@Setter
@NoArgsConstructor
public class Empleado {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "empleados_seq")
    @SequenceGenerator(name = "empleados_seq", sequenceName = "empleados_seq", allocationSize = 50)
    private Long id;

    @Column(name = "tenant_id", nullable = false, length = 40)
    private String tenantId;

    @Column(name = "empleado_id", nullable = false, length = 40)
    private String empleadoId;

    @Column(length = 120)
    private String nombres;

    @Column(length = 120)
    private String apellidos;

    @Column(length = 20)
    private String documento;

    @Column(length = 160)
    private String email;

    @Column(length = 80)
    private String area;

    @Column(length = 80)
    private String cargo;

    @Column(name = "jefe_id", length = 40)
    private String jefeId;

    private LocalDate fechaIngreso;

    private LocalDate fechaCese;

    @Column(precision = 12, scale = 2)
    private BigDecimal salarioBase;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private EstadoEmpleado estado;

    private Integer diasVacacionesAsignados;

    private Integer diasVacacionesUsados;

    private Instant actualizadoEn;

    @Version
    private Long version;

    public String getNombreCompleto() {
        String n = ((nombres == null ? "" : nombres) + " " + (apellidos == null ? "" : apellidos)).trim();
        return n.isEmpty() ? empleadoId : n;
    }
}
