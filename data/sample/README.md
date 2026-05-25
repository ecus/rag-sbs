# Sample data

## ⚠️ Importante

Los archivos con prefijo `MOCK_*` son **sintéticos**, generados como muestra
para validar el pipeline. **NO son fuente regulatoria**. Reemplazar por PDFs
descargados directamente de **sbs.gob.pe** antes de cualquier demo, eval RAGAS
o presentación de portafolio.

## Cómo cargar

```bash
make local-ingest
```

## Cómo poblar con documentos reales

1. Visita https://www.sbs.gob.pe/regulacion (corpus público)
2. Descarga 3–5 resoluciones cortas en PDF
3. Colócalos en este directorio
4. Ejecuta `make local-ingest`

El nombre del archivo se usa como `document_id`. Sugerencia: `Res-SBS-11356-2008.pdf`.

## Borrar muestras sintéticas

Cuando tengas PDFs reales, **elimina los `MOCK_*`** del repo y de la BD:

```bash
rm data/sample/MOCK_*
make psql
> DELETE FROM chunks WHERE document_id IN
    (SELECT id FROM documents WHERE document_id LIKE 'mock_%');
> DELETE FROM documents WHERE document_id LIKE 'mock_%';
```
