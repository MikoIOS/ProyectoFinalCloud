package com.example.backend_b;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

/** Verifica que el contexto de Spring levanta (H2 en memoria, sin datos ficticios). */
@SpringBootTest(properties = "hcm.seed.habilitado=false")
class BackendBApplicationTests {

    @Test
    void contextLoads() {
    }

}
