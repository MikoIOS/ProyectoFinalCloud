package com.example.backend_b.entities;

import com.example.backend_b.common.Enums.EstadoNomina;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/** Boleta de un empleado en un periodo (FASE1 §4.3). El detalle va en NominaDetalle. */
@Entity
@Table(name = "nominas",
        uniqueConstraints = {@UniqueConstraint(name = "uk_nominas_tenant_periodo_empleado", columnNames = {"tenant_id", "periodo", "empleado_id"})},
        indexes = {@Index(name = "ix_nominas_tenant_empleado", columnList = "tenant_id, empleado_id")})
@Getter
@Setter
@NoArgsConstructor
public class Nomina {

    @Id
    @GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "nominas_seq")
    @SequenceGenerator(name = "nominas_seq", sequenceName = "nominas_seq", allocationSize = 50)
    private Long id;

    @Column(name = "tenant_id", nullable = false, length = 40)
    private String tenantId;

    @Column(name = "periodo", nullable = false, length = 7)
    private String periodo;

    @Column(name = "empleado_id", nullable = false, length = 40)
    private String empleadoId;

    @Column(length = 200)
    private String nombreEmpleado;

    @Column(length = 20)
    private String documento;

    @Column(length = 80)
    private String area;

    @Column(length = 80)
    private String cargo;

    @Column(precision = 12, scale = 2)
    private BigDecimal salarioMensual;

    private Integer diasLaborados;

    @Column(precision = 12, scale = 2)
    private BigDecimal sueldoBase;

    @Column(precision = 12, scale = 2)
    private BigDecimal bonos;

    @Column(precision = 12, scale = 2)
    private BigDecimal descuentos;

    @Column(precision = 12, scale = 2)
    private BigDecimal neto;

    @Column(precision = 12, scale = 2)
    private BigDecimal aporteEssalud;

    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private EstadoNomina estado;

    private Instant generadoEn;

    @OneToMany(mappedBy = "nomina", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("orden ASC")
    private List<NominaDetalle> detalle = new ArrayList<>();

    @Version
    private Long version;

    public void agregarLinea(NominaDetalle linea) {
        linea.setNomina(this);
        linea.setOrden(detalle.size());
        detalle.add(linea);
    }
}
