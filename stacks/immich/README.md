# Immich

Fototeca con el servidor de Immich, aprendizaje automático por CPU, PostgreSQL con VectorChord y Valkey. Solo la web publica un puerto, `127.0.0.1:2283`. Las imágenes y la revisión de los modelos corresponden al [Compose de Immich v3.4.2](https://github.com/immich-app/immich/releases/tag/v3.4.2).

## Primer arranque

Desde `stacks/immich/` en la VM Debian, prepara el archivo privado con `test -e .env || install -m 600 .env.example .env`. En la primera instalación, genera la contraseña con `openssl rand -hex 32` y ponla en `DB_PASSWORD` antes de inicializar PostgreSQL.

- `UPLOAD_LOCATION` contiene la fototeca completa, incluidos los originales, las miniaturas y los vídeos transcodificados.
- `DB_DATA_LOCATION` contiene PostgreSQL. Usa un sistema de archivos Linux en disco local, preferiblemente SSD. Para el servicio de aprendizaje automático en esta VM x86, el modelo de CPU de Proxmox debe exponer al menos x86-64-v2. Immich recomienda 8 GB de RAM para su stack. [Requisitos de Immich](https://docs.immich.app/install/requirements/)

Crea los dos directorios antes de arrancar. Estos comandos usan las rutas de la plantilla. Si las cambias, comprueba el montaje del disco y crea las rutas elegidas.

```bash
mkdir -p ./runtime/library ./runtime/postgres
docker compose config --quiet
docker compose up -d --wait
curl -fsS http://127.0.0.1:2283/api/server/ping
```

Abre el túnel `ssh -N -L 2283:127.0.0.1:2283 usuario@vm` desde tu equipo y entra en `http://localhost:2283`. La primera cuenta es administradora. Sube una foto de prueba, abre su miniatura y descarga el original.

## Copia y recuperación

Para una copia en frío, detén todo el stack con `docker compose stop`, copia `UPLOAD_LOCATION`, `DB_DATA_LOCATION` y `.env` al mismo destino en otro disco, conservando propietarios y permisos. Arranca de nuevo con `docker compose up -d --wait`. El volumen `model-cache` se regenera al descargar los modelos.

Restaura ambas carpetas de la misma copia en rutas vacías, recupera `.env` y arranca con las mismas imágenes. Comprueba que la cuenta conserva sus álbumes y descarga un original. Para recuperar desde un volcado lógico, Immich también guarda copias de la base bajo `UPLOAD_LOCATION/backups`. Los originales se recuperan desde la copia de la fototeca. [Recuperación de Immich](https://docs.immich.app/administration/backup-and-restore/)
