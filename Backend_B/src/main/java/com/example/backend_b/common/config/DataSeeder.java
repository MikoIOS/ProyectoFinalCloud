package com.example.backend_b.common.config;

import com.example.backend_b.common.Enums.EstadoAusencia;
import com.example.backend_b.common.Enums.EstadoEmpleado;
import com.example.backend_b.common.Enums.EstadoMarcacion;
import com.example.backend_b.common.Enums.EstadoNomina;
import com.example.backend_b.common.Enums.EstadoPlanilla;
import com.example.backend_b.common.Enums.OrigenConcepto;
import com.example.backend_b.common.Enums.TipoAusencia;
import com.example.backend_b.common.Enums.TipoConcepto;
import com.example.backend_b.common.Utils;
import com.example.backend_b.entities.Ausencia;
import com.example.backend_b.entities.BandaSalarial;
import com.example.backend_b.entities.ConceptoNomina;
import com.example.backend_b.entities.Empleado;
import com.example.backend_b.entities.Marcacion;
import com.example.backend_b.entities.Nomina;
import com.example.backend_b.entities.Planilla;
import com.example.backend_b.infrastructure.repositories.AusenciaRepository;
import com.example.backend_b.infrastructure.repositories.BandaSalarialRepository;
import com.example.backend_b.infrastructure.repositories.ConceptoNominaRepository;
import com.example.backend_b.infrastructure.repositories.EmpleadoRepository;
import com.example.backend_b.infrastructure.repositories.MarcacionRepository;
import com.example.backend_b.infrastructure.repositories.NominaRepository;
import com.example.backend_b.infrastructure.repositories.PlanillaRepository;
import com.example.backend_b.services.CalculoNominaService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.Normalizer;
import java.time.Clock;
import java.time.DayOfWeek;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.YearMonth;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Random;

/**
 * Datos ficticios para los tenants de prueba (andina, pacifico, sierra). Solo corre si la tabla de
 * empleados está vacía y hcm.seed.habilitado=true. Es determinista (misma semilla ⇒ mismos datos).
 *
 * <p>Con hcm.seed.empleados-por-tenant=10000 se generan ≥ 30,000 registros por microservicio:
 * ~58k nóminas (2 meses) en nóminas y ~30k ausencias + ~29k marcaciones en asistencia.
 *
 * <p>Convención de IDs (para coincidir con ms-empleados): emp-000001 = Gerente General;
 * emp-000002..000007 = jefes de área (RR.HH., Tecnología, Finanzas, Ventas, Operaciones, Logística).
 */
@Component
@ConditionalOnProperty(name = "hcm.seed.habilitado", havingValue = "true")
public class DataSeeder implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);

    record Cargo(String nombre, int min, int max) {}

    record Area(String nombre, int peso, Cargo jefe, List<Cargo> cargos) {}

    static final Cargo GERENTE_GENERAL = new Cargo("Gerente General", 15000, 20000);
    static final List<Area> AREAS = List.of(
            new Area("Recursos Humanos", 6, new Cargo("Jefe de RR.HH.", 7000, 9500),
                    List.of(new Cargo("Analista de Nóminas", 3000, 4500), new Cargo("Asistente de RR.HH.", 1800, 2600),
                            new Cargo("Reclutador", 2500, 3800))),
            new Area("Tecnología", 12, new Cargo("Jefe de Tecnología", 9000, 13000),
                    List.of(new Cargo("Desarrollador Backend", 4500, 7500), new Cargo("Desarrollador Frontend", 4000, 7000),
                            new Cargo("Analista QA", 3200, 5000))),
            new Area("Finanzas", 8, new Cargo("Jefe de Finanzas", 8500, 12000),
                    List.of(new Cargo("Contador", 3800, 5500), new Cargo("Asistente Contable", 1800, 2700))),
            new Area("Ventas", 20, new Cargo("Jefe Comercial", 8000, 11000),
                    List.of(new Cargo("Ejecutivo de Ventas", 2500, 4500), new Cargo("Asesor Comercial", 1500, 2500))),
            new Area("Operaciones", 39, new Cargo("Jefe de Operaciones", 8000, 11000),
                    List.of(new Cargo("Supervisor de Operaciones", 3500, 5000), new Cargo("Operario", 1130, 1800),
                            new Cargo("Técnico de Mantenimiento", 2200, 3400))),
            new Area("Logística", 15, new Cargo("Jefe de Logística", 7500, 10000),
                    List.of(new Cargo("Almacenero", 1300, 1900), new Cargo("Analista de Logística", 2800, 4200))));

    static final String[] NOMBRES = {"María", "José", "Luis", "Rosa", "Carlos", "Ana", "Jorge", "Lucía", "Miguel", "Carmen",
            "Juan", "Elena", "Pedro", "Sofía", "Diego", "Valeria", "Fernando", "Camila", "Ricardo", "Daniela", "Andrés",
            "Patricia", "Jesús", "Gabriela", "Víctor", "Milagros", "César", "Fiorella", "Raúl", "Claudia", "Hugo", "Karina",
            "Óscar", "Mónica", "Renzo", "Andrea", "Alonso", "Jimena", "Sebastián", "Natalia"};
    static final String[] APELLIDOS = {"Quispe", "Huamán", "Mamani", "Flores", "Rodríguez", "García", "Sánchez", "Rojas",
            "Chávez", "Torres", "Ramos", "Vargas", "Castillo", "Mendoza", "Gutiérrez", "Espinoza", "Díaz", "Ccori", "Condori",
            "Paredes", "Salazar", "Romero", "Cruz", "Vásquez", "Ríos", "Gómez", "Pacheco", "Alvarado", "Zapata", "Medina",
            "Silva", "Herrera", "Aguilar", "Valverde", "Cárdenas", "Ticona", "Navarro", "Calderón", "Benites", "Palomino"};

    private final EmpleadoRepository empleadoRepo;
    private final NominaRepository nominaRepo;
    private final PlanillaRepository planillaRepo;
    private final ConceptoNominaRepository conceptoRepo;
    private final BandaSalarialRepository bandaRepo;
    private final AusenciaRepository ausenciaRepo;
    private final MarcacionRepository marcacionRepo;
    private final CalculoNominaService calculo;
    private final TransactionTemplate tx;
    private final Clock clock;
    private final ZoneId zona;

    @Value("${hcm.seed.tenants:andina,pacifico,sierra}")
    private String tenants;
    @Value("${hcm.seed.empleados-por-tenant:50}")
    private int empleadosPorTenant;
    @Value("${hcm.seed.meses-planilla:2}")
    private int mesesPlanilla;
    @Value("${hcm.seed.dias-marcacion:5}")
    private int diasMarcacion;
    @Value("${hcm.seed.ausencias-por-empleado:1}")
    private int ausenciasPorEmpleado;
    @Value("${hcm.seed.semilla:2032}")
    private long semilla;

    public DataSeeder(EmpleadoRepository empleadoRepo, NominaRepository nominaRepo, PlanillaRepository planillaRepo,
                      ConceptoNominaRepository conceptoRepo, BandaSalarialRepository bandaRepo, AusenciaRepository ausenciaRepo,
                      MarcacionRepository marcacionRepo, CalculoNominaService calculo, PlatformTransactionManager txManager,
                      Clock clock, ZoneId zona) {
        this.empleadoRepo = empleadoRepo;
        this.nominaRepo = nominaRepo;
        this.planillaRepo = planillaRepo;
        this.conceptoRepo = conceptoRepo;
        this.bandaRepo = bandaRepo;
        this.ausenciaRepo = ausenciaRepo;
        this.marcacionRepo = marcacionRepo;
        this.calculo = calculo;
        this.tx = new TransactionTemplate(txManager);
        this.clock = clock;
        this.zona = zona;
    }

    @Override
    public void run(String... args) {
        if (empleadoRepo.count() > 0) {
            log.info("DataSeeder: ya hay datos, no se genera nada");
            return;
        }
        long inicio = System.currentTimeMillis();
        LocalDate hoy = LocalDate.now(clock.withZone(zona));
        for (String t : tenants.split(",")) {
            String tenant = t.trim();
            List<Empleado> empleados = empleados(tenant, hoy);
            guardar(empleadoRepo, empleados);
            guardar(bandaRepo, bandas(tenant));
            nominas(tenant, empleados, hoy);
            asistencia(tenant, empleados, hoy);
            log.info("DataSeeder: tenant {} listo ({} empleados)", tenant, empleados.size());
        }
        log.info("DataSeeder: empleados={} nominas={} ausencias={} marcaciones={} en {} s",
                empleadoRepo.count(), nominaRepo.count(), ausenciaRepo.count(), marcacionRepo.count(),
                (System.currentTimeMillis() - inicio) / 1000);
    }

    private <T> void guardar(JpaRepository<T, Long> repo, List<T> items) {
        for (int i = 0; i < items.size(); i += 1000) {
            List<T> lote = items.subList(i, Math.min(items.size(), i + 1000));
            tx.executeWithoutResult(s -> repo.saveAll(lote));
        }
    }

    // ------------------------------------------------------------------ empleados

    List<Empleado> empleados(String tenant, LocalDate hoy) {
        Random r = new Random(semilla ^ tenant.hashCode());
        List<Empleado> out = new ArrayList<>();
        for (int i = 1; i <= empleadosPorTenant; i++) {
            Area area;
            Cargo cargo;
            String jefe;
            if (i == 1) {
                area = null;
                cargo = GERENTE_GENERAL;
                jefe = null;
            } else if (i <= 1 + AREAS.size()) {
                area = AREAS.get(i - 2);
                cargo = area.jefe();
                jefe = "emp-000001";
            } else {
                area = areaAleatoria(r);
                cargo = area.cargos().get(r.nextInt(area.cargos().size()));
                jefe = String.format("emp-%06d", 2 + AREAS.indexOf(area));
            }
            Empleado e = new Empleado();
            e.setTenantId(tenant);
            e.setEmpleadoId(String.format("emp-%06d", i));
            e.setNombres(NOMBRES[r.nextInt(NOMBRES.length)]);
            e.setApellidos(APELLIDOS[r.nextInt(APELLIDOS.length)] + " " + APELLIDOS[r.nextInt(APELLIDOS.length)]);
            e.setDocumento(String.valueOf(40000000 + r.nextInt(39999999)));
            e.setEmail(slug(e.getNombres()) + "." + slug(e.getApellidos().split(" ")[0]) + i + "@" + tenant + ".pe");
            e.setArea(area == null ? "Gerencia" : area.nombre());
            e.setCargo(cargo.nombre());
            e.setJefeId(jefe);
            e.setSalarioBase(BigDecimal.valueOf((cargo.min() + r.nextInt(Math.max(1, cargo.max() - cargo.min()))) / 50 * 50L).setScale(2));
            e.setFechaIngreso(i <= 1 + AREAS.size() ? LocalDate.of(2016 + r.nextInt(4), 1 + r.nextInt(12), 1 + r.nextInt(28))
                    : hoy.minusDays(30 + r.nextInt(365 * 9)));
            e.setEstado(EstadoEmpleado.ACTIVO);
            if (i > 1 + AREAS.size() && r.nextInt(100) < 3) {
                LocalDate c = e.getFechaIngreso().plusDays(60 + r.nextInt(900));
                if (!c.isBefore(hoy)) c = hoy.minusDays(1 + r.nextInt(20));
                if (!c.isAfter(e.getFechaIngreso())) c = e.getFechaIngreso().plusDays(1);
                e.setEstado(EstadoEmpleado.CESADO);
                e.setFechaCese(c);
            }
            e.setDiasVacacionesAsignados(30);
            e.setDiasVacacionesUsados(0);
            e.setActualizadoEn(clock.instant());
            out.add(e);
        }
        return out;
    }

    private static Area areaAleatoria(Random r) {
        int total = AREAS.stream().mapToInt(Area::peso).sum();
        int x = r.nextInt(total);
        for (Area a : AREAS) {
            x -= a.peso();
            if (x < 0) return a;
        }
        return AREAS.get(AREAS.size() - 1);
    }

    private List<BandaSalarial> bandas(String tenant) {
        List<Cargo> cargos = new ArrayList<>();
        cargos.add(GERENTE_GENERAL);
        AREAS.forEach(a -> { cargos.add(a.jefe()); cargos.addAll(a.cargos()); });
        List<BandaSalarial> out = new ArrayList<>();
        for (Cargo c : cargos) {
            BandaSalarial b = new BandaSalarial();
            b.setTenantId(tenant);
            b.setCargo(c.nombre());
            b.setMinimo(BigDecimal.valueOf(c.min()).setScale(2));
            b.setMaximo(BigDecimal.valueOf(c.max()).setScale(2));
            b.setMoneda("PEN");
            b.setActualizadoEn(clock.instant());
            out.add(b);
        }
        return out;
    }

    // ------------------------------------------------------------------ nóminas (meses cerrados, PAGADAS)

    private void nominas(String tenant, List<Empleado> empleados, LocalDate hoy) {
        Random r = new Random(semilla * 31 + tenant.hashCode());
        for (int m = mesesPlanilla; m >= 1; m--) {
            YearMonth periodo = YearMonth.from(hoy).minusMonths(m);
            Instant pago = periodo.atEndOfMonth().atTime(8, 0).toInstant(ZoneOffset.UTC);
            List<ConceptoNomina> conceptos = new ArrayList<>();
            List<Nomina> nominas = new ArrayList<>();
            BigDecimal bruto = BigDecimal.ZERO, desc = BigDecimal.ZERO, neto = BigDecimal.ZERO, essalud = BigDecimal.ZERO;
            for (Empleado e : empleados) {
                List<ConceptoNomina> delEmpleado = new ArrayList<>();
                if (r.nextInt(100) < 12) {
                    ConceptoNomina c = new ConceptoNomina();
                    c.setTenantId(tenant);
                    c.setEmpleadoId(e.getEmpleadoId());
                    c.setPeriodo(periodo.toString());
                    c.setTipo(TipoConcepto.BONO);
                    c.setConcepto(r.nextBoolean() ? "Bono por desempeño" : "Bono por productividad");
                    c.setMonto(BigDecimal.valueOf(100 + r.nextInt(8) * 50L).setScale(2));
                    c.setOrigen(OrigenConcepto.MANUAL);
                    c.setCreadoEn(pago);
                    delEmpleado.add(c);
                    conceptos.add(c);
                }
                Nomina n = calculo.calcular(e, periodo, delEmpleado);
                if (n == null) continue;
                n.setEstado(EstadoNomina.PAGADO);
                n.setGeneradoEn(pago);
                nominas.add(n);
                bruto = bruto.add(n.getSueldoBase()).add(n.getBonos());
                desc = desc.add(n.getDescuentos());
                neto = neto.add(n.getNeto());
                essalud = essalud.add(n.getAporteEssalud());
            }
            guardar(conceptoRepo, conceptos);
            guardar(nominaRepo, nominas);
            Planilla p = new Planilla();
            p.setTenantId(tenant);
            p.setPeriodo(periodo.toString());
            p.setEstado(EstadoPlanilla.PAGADA);
            p.setEjecucionId("seed");
            p.setTotalEmpleados(nominas.size());
            p.setProcesados(nominas.size());
            p.setTotalBruto(Utils.dinero(bruto));
            p.setTotalDescuentos(Utils.dinero(desc));
            p.setTotalNeto(Utils.dinero(neto));
            p.setTotalEssalud(Utils.dinero(essalud));
            p.setIniciadoEn(pago);
            p.setCompletadoEn(pago.plusSeconds(300));
            p.setSolicitadoPor("seed");
            planillaRepo.save(p);
        }
    }

    // ------------------------------------------------------------------ asistencia

    private void asistencia(String tenant, List<Empleado> empleados, LocalDate hoy) {
        Random r = new Random(semilla * 17 + tenant.hashCode());
        List<LocalDate> habiles = new ArrayList<>();
        for (LocalDate d = hoy.minusDays(1); habiles.size() < diasMarcacion; d = d.minusDays(1)) {
            if (d.getDayOfWeek() != DayOfWeek.SATURDAY && d.getDayOfWeek() != DayOfWeek.SUNDAY) habiles.add(d);
        }
        TipoAusencia[] tipos = {TipoAusencia.VACACIONES, TipoAusencia.VACACIONES, TipoAusencia.VACACIONES,
                TipoAusencia.PERMISO, TipoAusencia.LICENCIA_MEDICA, TipoAusencia.SIN_GOCE};
        List<Ausencia> ausencias = new ArrayList<>();
        List<Marcacion> marcaciones = new ArrayList<>();
        for (Empleado e : empleados) {
            boolean activo = e.getEstado() == EstadoEmpleado.ACTIVO;
            int usados = 0;
            LocalDate cursor = hoy.minusDays(360);
            for (int k = 0; k < ausenciasPorEmpleado; k++) {
                TipoAusencia tipo = tipos[r.nextInt(tipos.length)];
                int dias = switch (tipo) {
                    case VACACIONES -> 3 + r.nextInt(8);
                    case LICENCIA_MEDICA -> 1 + r.nextInt(5);
                    default -> 1 + r.nextInt(2);
                };
                LocalDate desde = cursor.plusDays(r.nextInt(Math.max(1, 300 / Math.max(1, ausenciasPorEmpleado))));
                boolean futura = activo && r.nextInt(100) < 6;
                if (futura) desde = hoy.plusDays(7 + r.nextInt(60));
                LocalDate hasta = desde.plusDays(dias - 1);
                cursor = hasta.plusDays(2);
                EstadoAusencia estado = futura ? EstadoAusencia.PENDIENTE : (r.nextInt(100) < 88 ? EstadoAusencia.APROBADA : EstadoAusencia.RECHAZADA);
                if (tipo == TipoAusencia.VACACIONES && estado == EstadoAusencia.APROBADA) {
                    if (usados + dias > 30) estado = EstadoAusencia.RECHAZADA; else usados += dias;
                }
                Ausencia a = new Ausencia();
                a.setTenantId(tenant);
                a.setEmpleadoId(e.getEmpleadoId());
                a.setNombreEmpleado(e.getNombreCompleto());
                a.setTipo(tipo);
                a.setConGoce(tipo.isConGoce());
                a.setDesde(desde);
                a.setHasta(hasta);
                a.setDias(dias);
                a.setMotivo(switch (tipo) {
                    case VACACIONES -> "Vacaciones programadas";
                    case LICENCIA_MEDICA -> "Descanso médico";
                    case SIN_GOCE -> "Asunto personal";
                    default -> "Trámite personal";
                });
                a.setEstado(estado);
                a.setAprobadorId(e.getJefeId());
                a.setSolicitadoPor("seed");
                a.setSolicitadoEn(desde.minusDays(10).atStartOfDay().toInstant(ZoneOffset.UTC));
                if (estado != EstadoAusencia.PENDIENTE) {
                    a.setResueltoEn(desde.minusDays(8).atStartOfDay().toInstant(ZoneOffset.UTC));
                    a.setResueltoPorEmpleado(e.getJefeId());
                }
                ausencias.add(a);
            }
            e.setDiasVacacionesUsados(usados);
            if (!activo) continue;
            for (LocalDate d : habiles) {
                if (r.nextInt(100) < 4) continue; // faltas ocasionales
                LocalTime entrada = LocalTime.of(8, 30).plusMinutes(r.nextInt(55));
                LocalTime salida = LocalTime.of(17, 45).plusMinutes(r.nextInt(80));
                int tard = (int) Math.max(0, Duration.between(LocalTime.of(9, 10), entrada).toMinutes());
                Marcacion m = new Marcacion();
                m.setTenantId(tenant);
                m.setEmpleadoId(e.getEmpleadoId());
                m.setFecha(d);
                m.setHoraEntrada(entrada);
                m.setHoraSalida(salida);
                m.setHoras(BigDecimal.valueOf(Duration.between(entrada, salida).toMinutes()).divide(BigDecimal.valueOf(60), 2, RoundingMode.HALF_UP));
                m.setTardanzaMinutos(tard);
                m.setTarde(tard > 0);
                m.setEstado(EstadoMarcacion.CERRADA);
                m.setArea(e.getArea());
                m.setOrigen("AUTOSERVICIO");
                m.setRegistradoPor("seed");
                marcaciones.add(m);
            }
        }
        guardar(empleadoRepo, empleados); // días de vacaciones usados
        guardar(ausenciaRepo, ausencias);
        guardar(marcacionRepo, marcaciones);
    }

    private static String slug(String s) {
        return Normalizer.normalize(s, Normalizer.Form.NFD).replaceAll("\\p{M}", "").toLowerCase(Locale.ROOT).replace(' ', '.');
    }
}
