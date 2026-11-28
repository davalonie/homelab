# Overleaf Extended Community Edition (CE+)

El stack usa la imagen de `yu-i-i/overleaf-cep`, MongoDB con un conjunto de réplicas de un miembro y Redis con persistencia. La web escucha en `127.0.0.1:8082`. Esta configuración está pensada para los usuarios de confianza del homelab. La compilación LaTeX se ejecuta dentro del contenedor de Overleaf. [Edición e imagen CE+](https://github.com/yu-i-i/overleaf-cep/wiki/Extended-CE:-Installation) · [Aislamiento de compilaciones](https://github.com/yu-i-i/overleaf-cep/wiki/Extended-CE:-Sandboxed-Compiles)

## Primer arranque

Desde `stacks/overleaf/` en la VM Debian, prepara el archivo privado con `test -e .env || install -m 600 .env.example .env`. En la primera instalación, genera un secreto con `openssl rand -base64 32` y guárdalo en `OVERLEAF_INVITE_TOKEN_SECRET`. Se utiliza para los enlaces de invitación. MongoDB 8 necesita que la VM x86 exponga AVX. El tipo de CPU `host` de Proxmox permite usar las instrucciones del miniPC.

```bash
docker compose config --quiet
docker compose up -d --wait
curl -fsS http://127.0.0.1:8082/status
```

MongoDB inicializa el conjunto `overleaf` al arrancar con un directorio vacío. La aplicación espera a que MongoDB sea primario y Redis esté disponible. Abre el túnel `ssh -N -L 8082:127.0.0.1:8082 usuario@vm` y entra en `http://localhost:8082/launchpad` para crear el primer administrador. Inicia sesión, crea un proyecto en blanco y compílalo hasta obtener el PDF. El autorregistro está cerrado.

Cuando publiques el servicio por HTTPS, ajusta `OVERLEAF_SITE_URL` al origen definitivo y añade `OVERLEAF_SECURE_COOKIE=true` a `.env`. En la prueba HTTP local deja esa variable sin definir.

## Copia y recuperación

Detén los tres servicios con `docker compose stop`. Copia a otro disco `.env` y todo `OVERLEAF_DATA_DIR`, incluidos `overleaf/` (archivos e historial), `mongo/` (usuarios y proyectos) y `redis/` (estado persistente de edición). Conserva propietarios y permisos. Vuelve a arrancar con `docker compose up -d --wait`.

Para verificar la recuperación, restaura el mismo conjunto en un directorio vacío, usa las mismas imágenes y conserva el nombre interno `mongo` del miembro de la réplica. Abre un proyecto existente, comprueba su historial y recompila el PDF.
