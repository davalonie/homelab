# Acceso privado por HTTPS

Habilita el reenvío en el LXC de Tailscale, anuncia y aprueba la ruta de subred y limita el acceso de los clientes autorizados al DNS privado y al HTTPS de Caddy. En Pi-hole, cada nombre de aplicación debe resolver a la IP del LXC de Caddy alcanzable por esa ruta.

## Preparar los backends de la VM

En el `.env` de cada stack, cambia la variable de escucha de `127.0.0.1` a la IP privada de la VM. Restringe el acceso a esos puertos al LXC de Caddy desde el cortafuegos de Proxmox o mediante reglas efectivas sobre el tráfico de Docker. Aplica los cambios con `docker compose up -d --wait` desde el directorio del stack.

| Servicio | Variable de escucha | Puerto por defecto | Configuración de la aplicación |
| --- | --- | --- | --- |
| Armonía | `MUSIC_BIND` | 18400 | Ajusta `MUSIC_PUBLIC_ORIGIN` al origen HTTPS y `MUSIC_PORT` al puerto publicado. |
| Jellyfin y Seerr | `MEDIA_BIND` | 8096 y 5055 | Añade la IP del LXC de Caddy a los proxies conocidos de Jellyfin. |
| Vaultwarden | `VAULTWARDEN_BIND` | 8222 | Pon el origen HTTPS de la bóveda en `VAULTWARDEN_URL`. |
| Immich | `IMMICH_BIND` | 2283 | Sirve la fototeca en la raíz de su propio subdominio. |
| Overleaf CE+ | `OVERLEAF_BIND` | 8082 | Ajusta `OVERLEAF_SITE_URL` al origen HTTPS y añade `OVERLEAF_SECURE_COOKIE=true`. |

## Configurar Caddy en su LXC

La plantilla usa un certificado comodín con el desafío DNS-01 de DuckDNS. Proxmox conserva el proxy HTTPS del despliegue actual, que omite la verificación del certificado del backend. Los demás servicios reciben HTTP por la red privada. [Caddyfile](../infra/caddy/Caddyfile) · [Módulo DuckDNS](https://github.com/caddy-dns/duckdns)

1. Lleva `infra/caddy/Caddyfile` y `infra/caddy/.env.example` a un directorio de preparación en el LXC. Desde ese directorio, como root, comprueba el módulo con `caddy list-modules | grep -Fx dns.providers.duckdns`. Para crear el archivo privado por primera vez usa `test -e /etc/caddy/.env || install -m 600 .env.example /etc/caddy/.env`. Si ya existe, incorpora las variables que falten y conserva el token actual.
2. Rellena `/etc/caddy/.env` con la zona privada, el dominio DuckDNS que ya usas para el desafío y el token. Cada `*_HOST` es un nombre completo bajo el comodín y cada `*_UPSTREAM` es una dirección con puerto, sin esquema. Las tres apps nuevas comparten la IP de la VM. El repositorio usa valores de ejemplo. [Plantilla de variables](../infra/caddy/.env.example)
3. Con `systemctl edit caddy`, añade la referencia al archivo en la sección de servicio. Si el `ExecStart` de tu unidad incluye `--environ`, añade al mismo bloque una línea `ExecStart=` y otra con el comando original quitando ese argumento. Así el arranque conserva tu binario con DuckDNS y evita imprimir el token en el diario. [Variables del servicio de Caddy](https://caddyserver.com/docs/running#environment-variables)

```ini
[Service]
EnvironmentFile=/etc/caddy/.env
```

4. Valida desde el directorio de preparación con `caddy validate --config ./Caddyfile --envfile /etc/caddy/.env`. Tras la validación, guarda una copia del Caddyfile activo en el LXC e instala la plantilla con `install -m 644 Caddyfile /etc/caddy/Caddyfile`. En la primera aplicación usa `systemctl restart caddy` para que el proceso reciba el entorno. Para cambios posteriores de rutas usa `systemctl reload caddy`. Si rotas el token DuckDNS, reinicia el servicio para que el módulo lea el nuevo valor.

Desde un cliente conectado a Tailscale, abre cada nombre por HTTPS y comprueba la confianza del certificado. Para verificar las rutas nuevas, consulta `/alive` en Vaultwarden, `/api/server/ping` en Immich y `/status` en Overleaf. Un nombre sin ruta dentro del comodín, si resuelve a Caddy, devuelve `404 Servicio no configurado`.
