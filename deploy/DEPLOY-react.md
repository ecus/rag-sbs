# Despliegue del frontend React a producción

Checklist para poner el nuevo frontend React como UI de usuario final, dejando
el panel Streamlit como **admin** en `/admin`. Pensado para ejecutarse en la VM
(`ubuntu@3.220.87.49`) en una ventana de mantenimiento.

## 0. Qué cambia
- `/` → SPA React (Consultar, Tópicos, Mapa, cuenta).
- `/admin` → Streamlit (panel de administración, sin cambios de código).
- `/v1`, `/api`, `/graph` → API (sin cambios).

## 1. Build del frontend
```bash
cd frontend
npm ci
npm run build         # genera frontend/dist (estático, ~360 KB gzip inicial)
```
Para actualizar el `dist` en la VM, sincronizar el directorio COMPLETO (no borrar
archivos a mano — los chunks lazy Mapa/Topicos NO están referenciados en index.html
y un borrado manual los eliminaría). Usar rsync con --delete para limpiar huérfanos:
```bash
rsync -az --delete frontend/dist/ ubuntu@VM:/opt/rag-sbs/frontend/dist/
```

## 2. Editar `docker-compose.prod.yml`
En el servicio **`caddy`**, reemplazar el montaje del Caddyfile y agregar el dist:
```yaml
    volumes:
      - ./deploy/Caddyfile.react:/etc/caddy/Caddyfile:ro   # <- cambia de Caddyfile a Caddyfile.react
      - ./frontend/dist:/srv/app:ro                         # <- nuevo
      - caddy-data:/data
      - caddy-config:/config
```
En el servicio **`ui`** (Streamlit), agregar al `command`:
```yaml
      - --server.baseUrlPath=admin
```

## 3. Deploy del backend (cambios ya en el código)
Estos cambios están en `src/api/routes_graph.py` y necesitan rebuild de la imagen `api`:
- `score` por arista en `/v1/graph/data` (mejora el umbral de enlaces del Mapa).
- Parámetro `max_edges_per_node` para sparsificar el grafo (evita el "ovillo").

## 4. Levantar
```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## 5. Verificar
- `https://consultasbs.eurrutia.dev/` → login React.
- `https://consultasbs.eurrutia.dev/admin` → Streamlit admin.
- Consultar (streaming), Tópicos, Mapa (modo Explorar), feedback, recovery PIN,
  eliminar cuenta, encuesta al cerrar sesión.
- Refrescar (F5) estando logueado: la sesión persiste (localStorage).

## Rollback
Volver a montar `./deploy/Caddyfile` en el servicio `caddy`, quitar el volumen
`/srv/app` y el `--server.baseUrlPath=admin`, y `up -d` de nuevo.

## Pendientes conocidos (no bloquean el lanzamiento de usuario final)
- Construir clusters de tópicos (`POST /v1/graph/topics/build`) para poblar el
  grid de Tópicos y la vista de clusters del Mapa (costo Gemini).
- Corregir el mapeo de `issuer` en el grafo (colores por institución).
- Portar el panel admin a React con auth por token (para retirar Streamlit).
