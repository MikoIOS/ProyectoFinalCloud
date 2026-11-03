package com.example.backend_b.common.Enums;

public enum TipoAusencia {
    VACACIONES(true),
    PERMISO(true),
    LICENCIA_MEDICA(true),
    SIN_GOCE(false);

    private final boolean conGoce;

    TipoAusencia(boolean conGoce) {
        this.conGoce = conGoce;
    }

    public boolean isConGoce() {
        return conGoce;
    }
}
