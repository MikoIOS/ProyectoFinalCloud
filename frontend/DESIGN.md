# DESIGN.md — Portal HCM

## 0. Sources Phase 0

### 0a. Visual reference
Referencia explícita del usuario: Chiikawa, https://www.anime-chiikawa.jp/. Referencias consultadas en la conversación; ilustraciones propias construidas en CSS. Discovery produjo recibos locales y referencias externas limitadas, no una validación visual completa.

### 0b. Design intelligence
Portal operativo HCM. Se usa la investigación local de discovery para estados y navegación; se descarta su hipótesis de landing oscura por contradecir la instrucción del usuario.

### 0c. Rationale
Una libreta de trabajo con colores pastel y tinta oscura combina el tono solicitado con tablas de datos y formularios legibles.

## 1. Theme & Visual Concept

Papelería kawaii, crema, tabs rosa, mascotas pequeñas. Firma: welcome-notebook con ilustración y enlace funcional a asistencia.

## 2. Color Palette

| Role | Hex | Usage |
|---|---|---|
| Background | #FBF8F3 | Fondo crema |
| Surface | #FFFFFF | Tarjetas y formularios |
| Text | #4D4142 | Tinta principal |
| Muted | #76696A | Texto secundario |
| Accent | #A84C64 | Botones y foco, texto blanco |
| Pink | #F8E3E7 | Bienvenida y selección |
| Blue | #E5F0F7 | Estadísticas y mascota |
| Mint | #E7F1E7 | Éxito |

## 3. Typography

Display y body: Nunito, sistema sans-serif de respaldo. Fuente redondeada y cifras tabulares para importes.

## 4. Typography Hierarchy

- **H1**: 30px / 800
- **H2**: 24px / 800
- **H3**: 18px / 700
- **P**: 14px / 400 / 1.6
- **Small**: 12px / 700
Títulos nunca ocupan el lugar de datos.

## 5. Spacing & Grid

Base 8px, separación 24px, margen desktop 32px, móvil 16px; lateral 232px; tarjetas radio 24px y controles radio 16px.

## 6. Components & States

Botones de al menos 48px, acento berry con contraste. Cards con borde tenue y sombra pequeña. Skeletons conservan distribución y tamaño, sombras estáticas suaves. Error con reintento, vacío con explicación, éxito con datos reales y feedback. Tablas con scroll propio sin desbordar viewport.

## 7. Motion & Animations

Transiciones 150ms; skeletons estáticos para mantener calma visual. prefers-reduced-motion elimina animaciones. Nada de destellos o desplazamientos automáticos.

## 8. Dark Mode

Light-only por preferencia visual expresa. No se añade un modo no solicitado.

## 11. Signature Gesture

Owned move: libreta de bienvenida con mascotas originales, tabs y CTA de asistencia. Grep signature: welcome-notebook.

```json
{"id":"welcome-notebook","selector":"[data-wde-signature='welcome-notebook']","expected_behavior":"state_or_content_changes_on_interaction","desktop":true,"mobile":true,"minimum_visible_area":400,"description":"Libreta kawaii con CTA funcional a asistencia"}
```

## 12. Intentional Tensions

Ilustración tierna junto a datos reales; fondo pastel con tinta oscura; espacio generoso con tablas compactas.
