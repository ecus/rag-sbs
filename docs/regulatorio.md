---
title: Fuentes regulatorias
---

# Corpus regulatorio indexado

Todos los documentos del corpus se descargan de fuentes oficiales y se validan periódicamente contra el portal en línea de SBS y BCRP. Las URLs verificadas al **2026-05-20**:

## Resoluciones SBS

| Resolución | Año | Tema | URL oficial |
|---|---|---|---|
| **11356-2008** | 2008 | Reglamento para la Evaluación y Clasificación del Deudor | [PDF v6.0](https://intranet2.sbs.gob.pe/dv_int_cn/1097/v6.0/Adjuntos/11356-2008.r.pdf) |
| **14353-2009** | 2009 | Provisiones Genéricas | (SBS portal) |
| **14354-2009** | 2009 | Patrimonio Efectivo por Riesgo de Crédito | (SBS portal) |
| **2368-2023** | 2023 | Modifica Reglamento del Deudor (num. 2.2 corporativo) | [PDF](https://intranet2.sbs.gob.pe/dv_int_cn/2290/v2.0/Adjuntos/2368-2023.pdf) |
| **4345-2023** | 2023 | Modifica Cap. I Definiciones (rangos no cambian) | [PDF](https://intranet2.sbs.gob.pe/dv_int_cn/2326/v1.0/Adjuntos/04345-2023.R.pdf) |
| **975-2025** | 2025 | Modifica definiciones Cap. I (rangos no cambian) | [PDF](https://intranet2.sbs.gob.pe/dv_int_cn/2486/v1.0/Adjuntos/975-2025.R.pdf) |
| **5570-2019** | 2019 | Revolvente / no-revolvente, factores de conversión | (SBS portal) |
| **3780-2011** | 2011 | Evaluación Crediticia | (SBS portal) |
| **8181-2012** | 2012 | Reglamento de Transparencia | [PDF](https://intranet2.sbs.gob.pe/dv_int_cn/763/v4.0/adjuntos/8181-2012.R.pdf) |
| **1010-1999** | 1999 | Reglamento del Fideicomiso | (SBS portal) |
| **1308-2013** | 2013 | Transferencia de Cartera | (SBS portal) |
| **480-2019** | 2019 | Operaciones con Cartera | (SBS portal) |
| **2116-2009** | 2009 | Riesgo Operacional | (SBS portal) |
| **272-2017** | 2017 | Gobierno Corporativo | (SBS portal) |
| **504-2021** | 2021 | Reglamento SGSI / Ciberseguridad | (SBS portal) |
| **789-2018** | 2018 | PLAFT | (SBS portal) |
| **1802-2014** | 2014 | Cumplimiento Cooperativas | (SBS portal) |
| **3986-2024** | 2024 | (otro tema riesgo de crédito) | (SBS portal) |

## Circulares y Notas BCRP

| Documento | Fecha | Tema | URL oficial |
|---|---|---|---|
| **Circular 0008-2021-BCRP** | abril 2021 | Tasas máximas de interés convencional compensatorio y moratorio | [PDF](https://www.bcrp.gob.pe/docs/Transparencia/Normas-Legales/Circulares/2021/circular-0008-2021-bcrp.pdf) |
| Nota informativa 2025-10-09 | oct 2025 | Tasas vigentes para período abr 2025–oct 2025 | [PDF](https://www.bcrp.gob.pe/docs/Transparencia/Notas-Informativas/2025/nota-informativa-2025-10-09-2.pdf) |
| Nota informativa 2026-04-07 | abr 2026 | Tasas vigentes para período actual | [PDF](https://www.bcrp.gob.pe/docs/Transparencia/Notas-Informativas/2026/nota-informativa-2026-04-07.pdf) |

## Validación de vigencia

Las **tablas críticas de clasificación** (rangos de días de atraso por categoría) están **hardcoded** en `src/tools/clasificacion.py` y se validaron contra el texto literal del PDF oficial. Lo verificado:

### Hipotecario (Cap. II num. 4)

| Categoría | Rango (días) | Cita literal PDF |
|---|---|---|
| Normal | 0–30 | "atraso de hasta treinta (30) días calendario" |
| CPP | 31–60 | "treinta y uno (31) a sesenta (60) días" |
| Deficiente | 61–120 | "sesenta y uno (61) a ciento veinte (120) días" |
| Dudoso | 121–365 | "ciento veintiuno (121) a trescientos sesenta y cinco (365) días" |
| Pérdida | > 365 | "más de trescientos sesenta y cinco (365) días" |

### Minoristas no hipotecarios (Cap. II num. 3)

| Categoría | Rango (días) |
|---|---|
| Normal | 0–8 |
| CPP | 9–30 |
| Deficiente | 31–60 |
| Dudoso | 61–120 |
| Pérdida | > 120 |

### Corporativo / gran empresa / mediana empresa (Cap. II num. 2)

Clasificación **principalmente cualitativa** (capacidad de pago, flujo de caja). El componente cuantitativo de días:

| Categoría | Atraso (días) |
|---|---|
| Normal | 0 + evaluación cualitativa |
| CPP | hasta 60 (o atrasos > 15d × 2 en 6m) |
| Deficiente | 61–120 |
| Dudoso | 121–365 |
| Pérdida | > 365 |

## Tasas de provisión (Cap. III)

### Sin garantía preferida

| Categoría | Tasa |
|---|---|
| Normal | 0% (+ 1% provisión genérica) |
| CPP | 5.00% |
| Deficiente | 25.00% |
| Dudoso | 60.00% |
| Pérdida | 100.00% |

### Con garantía preferida

| Categoría | Tasa |
|---|---|
| Normal | 0% (+ 1% genérica) |
| CPP | 2.50% |
| Deficiente | 12.50% |
| Dudoso | 30.00% |
| Pérdida | 60.00% |

### Descuentos del Anexo II (haircuts)

| Tipo de garantía | Descuento aplicable |
|---|---|
| Preferida (ej. hipoteca) | 50% |
| Preferida muy rápida realización (oro, joyas) | 30% |
| Preferida autoliquidable (depósitos efectivo) | 0% |

## Política de actualización

El scheduler interno revisa **diariamente** los URLs registrados en `doc_sources` y detecta cambios por:
- `Last-Modified` del header HTTP
- ETag
- Hash SHA-256 del contenido descargado

Cuando hay un cambio, dispara un `ingest_run` que re-procesa el documento y emite un `change_event`.
