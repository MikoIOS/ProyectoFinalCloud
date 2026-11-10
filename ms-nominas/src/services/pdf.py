"""Generador de PDF de una página A4 sin dependencias externas.

Puerto directo de Backend_B/common/pdf/SimplePdf.java. Usa Helvetica / Helvetica-Bold
con WinAnsiEncoding para soportar tildes y ñ.
"""
from decimal import Decimal

ANCHO = 595.0
ALTO = 842.0


def _fmt(valor):
    if float(valor) == int(float(valor)):
        return str(int(float(valor)))
    return "%.2f" % float(valor)


def _ancho(texto, tamano, negrita):
    total = 0.0
    for c in texto:
        if c == " ":
            total += 0.278
        elif c in ".,:ilI":
            total += 0.28
        elif c.isdigit():
            total += 0.556
        elif c.isupper():
            total += 0.72 if negrita else 0.667
        else:
            total += 0.6 if negrita else 0.556
    return total * tamano


def _escapar(texto):
    salida = []
    for c in str(texto):
        if c in "()\\":
            salida.append("\\" + c)
        elif ord(c) < 32:
            salida.append(" ")
        else:
            try:
                c.encode("cp1252")
                salida.append(c)
            except UnicodeEncodeError:
                salida.append("?")
    return "".join(salida)


class SimplePdf:
    def __init__(self):
        self.contenido = []

    def text(self, x, y, tamano, negrita, texto):
        fuente = "F2" if negrita else "F1"
        self.contenido.append(
            "BT /%s %s Tf %s %s Td (%s) Tj ET" % (fuente, _fmt(tamano), _fmt(x), _fmt(y), _escapar(texto))
        )
        return self

    def text_right(self, x_derecha, y, tamano, negrita, texto):
        return self.text(x_derecha - _ancho(str(texto), tamano, negrita), y, tamano, negrita, texto)

    def line(self, x1, y1, x2, y2, grosor):
        self.contenido.append("%s w %s %s m %s %s l S" % (_fmt(grosor), _fmt(x1), _fmt(y1), _fmt(x2), _fmt(y2)))
        return self

    def fill_rect(self, x, y, w, h, gris):
        self.contenido.append("q %s g %s %s %s %s re f Q" % (_fmt(gris), _fmt(x), _fmt(y), _fmt(w), _fmt(h)))
        return self

    def build(self):
        stream = "\n".join(self.contenido).encode("cp1252", errors="replace")
        objetos = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %s %s] "
                "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
                % (_fmt(ANCHO), _fmt(ALTO))
            ).encode("ascii"),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        ]
        salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, obj in enumerate(objetos, start=1):
            offsets.append(len(salida))
            salida += ("%d 0 obj\n" % i).encode("ascii")
            salida += obj
            salida += b"\nendobj\n"
        xref = len(salida)
        salida += ("xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)).encode("ascii")
        for off in offsets:
            salida += ("%010d 00000 n \n" % off).encode("ascii")
        salida += (
            "trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, xref)
        ).encode("ascii")
        return bytes(salida)


NOMBRES_TENANT = {
    "andina": "Corporación Andina S.A.C.",
    "pacifico": "Pacífico Servicios S.A.",
    "sierra": "Sierra Industrial S.A.C.",
}


def _nvl(valor):
    return valor if valor not in (None, "") else "-"


def _fmt_dinero(valor):
    return format(Decimal(str(valor or 0)), ",.2f")


def _lineas(nomina, tipo):
    return [d for d in nomina.get("detalle", []) if d.get("tipo") == tipo]


def _fila(pdf, izq, y, etiqueta, valor):
    pdf.text(izq, y, 9, True, etiqueta)
    pdf.text(izq + 140, y, 9, False, _nvl(valor))
    return y - 15


def _seccion(pdf, izq, der, y, titulo, lineas):
    if not lineas:
        return y
    pdf.fill_rect(izq, y - 5, der - izq, 17, 0.93)
    pdf.text(izq + 6, y, 9, True, titulo)
    pdf.text_right(der - 6, y, 9, True, "S/")
    y -= 18
    for linea in lineas:
        pdf.text(izq + 10, y, 9, False, linea.get("concepto", "-"))
        pdf.text_right(der - 6, y, 9, False, _fmt_dinero(linea.get("monto")))
        y -= 14
    return y - 8


def _total(pdf, izq, der, y, etiqueta, valor):
    pdf.text(izq + 10, y, 10, True, etiqueta)
    pdf.text_right(der - 10, y, 10, False, "S/ " + _fmt_dinero(valor))
    return y - 22


def generar(nomina):
    empresa = NOMBRES_TENANT.get(nomina.get("tenant_id"), nomina.get("tenant_id", ""))
    pdf = SimplePdf()
    izq, der = 50.0, ANCHO - 50.0
    y = 790.0

    pdf.fill_rect(izq, y - 8, der - izq, 34, 0.86)
    pdf.text(izq + 12, y + 4, 15, True, "BOLETA DE PAGO")
    pdf.text_right(der - 12, y + 4, 11, True, empresa.upper())
    y -= 40

    pdf.text(izq, y, 9, False, "Periodo: " + str(nomina.get("periodo", "")))
    pdf.text_right(der, y, 9, False, "N.º %s-%s" % (nomina.get("periodo", ""), nomina.get("empleado_id", "")))
    y -= 26

    y = _fila(pdf, izq, y, "Trabajador", nomina.get("nombre_empleado"))
    y = _fila(pdf, izq, y, "Código", nomina.get("empleado_id"))
    y = _fila(pdf, izq, y, "Documento", nomina.get("documento"))
    y = _fila(pdf, izq, y, "Área / Cargo", "%s / %s" % (_nvl(nomina.get("area")), _nvl(nomina.get("cargo"))))
    y = _fila(pdf, izq, y, "Días laborados", str(nomina.get("dias_laborados", 0)))
    y = _fila(pdf, izq, y, "Remuneración mensual", "S/ " + _fmt_dinero(nomina.get("salario_mensual")))
    y -= 10

    y = _seccion(pdf, izq, der, y, "INGRESOS", _lineas(nomina, "INGRESO"))
    y = _seccion(pdf, izq, der, y, "DESCUENTOS", _lineas(nomina, "DESCUENTO"))
    y = _seccion(pdf, izq, der, y, "APORTES DEL EMPLEADOR", _lineas(nomina, "APORTE_EMPLEADOR"))

    y -= 6
    pdf.line(izq, y, der, y, 0.8)
    y -= 18
    y = _total(pdf, izq, der, y, "Total ingresos", Decimal(str(nomina.get("sueldo_base", 0))) + Decimal(str(nomina.get("bonos", 0))))
    y = _total(pdf, izq, der, y, "Total descuentos", nomina.get("descuentos"))
    pdf.fill_rect(izq, y - 8, der - izq, 26, 0.9)
    pdf.text(izq + 10, y, 12, True, "NETO A PAGAR")
    pdf.text_right(der - 10, y, 12, True, "S/ " + _fmt_dinero(nomina.get("neto")))
    y -= 70

    pdf.line(izq + 20, y, izq + 200, y, 0.5)
    pdf.line(der - 200, y, der - 20, y, 0.5)
    pdf.text(izq + 70, y - 14, 8, False, "Empleador")
    pdf.text(der - 135, y - 14, 8, False, "Trabajador")
    pdf.text(izq, 40, 7, False, "Documento generado por HCM SaaS · ms-nominas · " + str(nomina.get("generado_en", "")))
    return pdf.build()
