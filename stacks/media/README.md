# Media

Seerr recibe peticiones, Radarr y Sonarr organizan películas y series, Prowlarr gestiona los indexadores, Bazarr añade subtítulos y Jellyfin reproduce la biblioteca. qBittorrent comparte la red de Gluetun para descargar por VPN. El stack funciona con cuentas locales.

## Preparar la VM Debian

Ejecuta los comandos desde `stacks/media/` con Python 3 y Docker Compose 2.24.4 o posterior. En una instalación nueva, crea el archivo local con `install -m 600 .env.example .env`. Ajusta `MEDIA_UID` y `MEDIA_GID` a la cuenta propietaria de los datos y elige las rutas antes de arrancar.

- `MEDIA_CONFIG_DIR` guarda las cuentas, bases de datos y ajustes en disco local. `MEDIA_CACHE_DIR` guarda la caché de Jellyfin.
- `MEDIA_DATA_DIR` contiene `torrents/` y `library/`. Coloca ambos en un mismo sistema de archivos para que Radarr y Sonarr puedan importar mediante enlaces duros y qBittorrent pueda seguir compartiendo el original. Si usas un disco dedicado, comprueba que está montado antes de crear los directorios.
- La plantilla de `.env` selecciona VPNBook por OpenVPN para las descargas. Si ya tienes un `.env` y quieres migrar, añade o actualiza `COMPOSE_FILE=compose.yaml:compose.vpnbook.yaml`. El servidor inicial es Francia 2 (`fr231.vpnbook.com`), por TCP 443. Puedes elegir Francia 1 con `MEDIA_VPNBOOK_SERVER=fr200.vpnbook.com`. Tailscale proporciona el acceso entrante al homelab. [Servidores y perfiles oficiales de VPNBook](https://www.vpnbook.com/freevpn/openvpn)

Prepara los directorios usando los valores de tu `.env`. La imagen de Seerr usa la cuenta interna 1000:1000. [Instalación de Seerr](https://docs.seerr.dev/getting-started/docker/)

```bash
. ./.env
sudo install -d -m 750 -o "$MEDIA_UID" -g "$MEDIA_GID" \
  "$MEDIA_CONFIG_DIR"/{jellyfin,radarr,sonarr,prowlarr,qbittorrent,bazarr} "$MEDIA_CACHE_DIR/jellyfin"
sudo install -d -m 750 -o 1000 -g 1000 "$MEDIA_CONFIG_DIR/seerr"
sudo install -d -m 2775 -o "$MEDIA_UID" -g "$MEDIA_GID" \
  "$MEDIA_DATA_DIR"/{torrents,library}/{movies,tv}
python3 scripts/vpnbook.py
docker compose config --quiet
docker compose up -d --wait
```

Si todavía estás eligiendo VPN, puedes arrancar `docker compose up -d --wait jellyfin seerr radarr sonarr prowlarr bazarr` y usar Jellyfin con contenido que ya tengas. FlareSolverr es opcional y su perfil se activa con `docker compose --profile flaresolverr up -d --wait`.

## Actualización automática de VPNBook

El script obtiene la contraseña pública y los certificados directamente de VPNBook, resuelve la IPv4 del servidor elegido y guarda cada versión completa en `secrets/vpnbook/`. Una vez establecido el túnel, Gluetun usa DNS sobre HTTPS para resolver los nombres que necesita qBittorrent.

Si el proveedor falla al publicar los datos, el túnel activo sigue con sus archivos anteriores. Con las descargas en marcha, Compose aplica los cambios a Gluetun y qBittorrent y espera a que estén sanos. Si la nueva configuración falla, el script intenta recuperar la anterior y registra el fallo para el siguiente intento. Con el stack apagado, sólo prepara los archivos. Si una actualización se interrumpe al recrear los contenedores, la siguiente ejecución recupera los servicios que estaban en marcha.

Instala el temporizador desde `stacks/media/` en la VM, como el usuario que ejecuta Compose.

```bash
install -d ~/.config/systemd/user
install -m 644 scripts/systemd/media-vpnbook@.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
timer=$(systemd-escape --path --template=media-vpnbook@.timer "$PWD")
systemctl --user enable --now "$timer"
systemctl --user list-timers "$timer"
```

Comprueba cada tres horas. Para que se ejecute tras reiniciar la VM aunque no abras sesión, habilita la persistencia del gestor de usuario con `loginctl enable-linger "$USER"`. Para comprobarlo inmediatamente, ejecuta `systemctl --user start "${timer%.timer}.service"` y consulta `journalctl --user -u "${timer%.timer}.service" -n 30`. Usa el mismo `.env` para el temporizador y para los arranques manuales, incluido `COMPOSE_PROJECT_NAME` si personalizas el nombre del proyecto.

### Usar tu propio perfil WireGuard

Selecciona `COMPOSE_FILE=compose.yaml` en el `.env`. Crea `secrets/` con `install -d -m 700 secrets`, copia el perfil con `install -m 600 /ruta/al/perfil.conf secrets/wg0.conf` y arranca con `docker compose up -d --wait`. Puedes usar otra ruta mediante `MEDIA_WG_FILE`. Usa un túnel completo con `AllowedIPs = 0.0.0.0/0` y un `Endpoint` con IP y puerto. Omite el paso `python3 scripts/vpnbook.py` en esta modalidad. Si habías habilitado el temporizador, desactívalo con `systemctl --user disable --now "$timer"`. [Proveedor WireGuard personalizado en Gluetun](https://github.com/qdm12/gluetun-wiki/blob/main/setup/providers/custom.md)

## Acceso privado

Por defecto las interfaces web escuchan en la VM a través de `127.0.0.1`. Para dar acceso a los usuarios, configura `MEDIA_BIND` con la IP privada de la VM, restringe sus puertos 8096 y 5055 al LXC de Caddy en el cortafuegos de Proxmox y publica un nombre HTTPS privado para cada uno. En Jellyfin añade la IP de Caddy en **Redes → Proxies conocidos**. [DNS privado y Caddy](../../docs/tailscale.md) · [Proxy inverso de Jellyfin](https://jellyfin.org/docs/general/post-install/networking/reverse-proxy/)

| Interfaz | Dirección desde la VM | Dirección entre contenedores |
| --- | --- | --- |
| Jellyfin | `MEDIA_BIND:8096` | `http://jellyfin:8096` |
| Seerr | `MEDIA_BIND:5055` | `http://seerr:5055` |
| Radarr | `127.0.0.1:7878` | `http://radarr:7878` |
| Sonarr | `127.0.0.1:8989` | `http://sonarr:8989` |
| Prowlarr | `127.0.0.1:9696` | `http://prowlarr:9696` |
| Bazarr | `127.0.0.1:6767` | `http://bazarr:6767` |
| qBittorrent | `127.0.0.1:8080` | `http://gluetun:8080` |

Para abrir los paneles de administración desde tu equipo, sustituye `usuario@vm` por tu acceso SSH y abre el puerto correspondiente en `localhost` mientras dure el túnel. Si Jellyfin y Seerr siguen en bucle local, añade `-L 8096:127.0.0.1:8096 -L 5055:127.0.0.1:5055` al comando antes de `usuario@vm`.

```sh
ssh -N -L 7878:127.0.0.1:7878 -L 8989:127.0.0.1:8989 -L 9696:127.0.0.1:9696 \
  -L 6767:127.0.0.1:6767 -L 8080:127.0.0.1:8080 usuario@vm
```

## Conectar las aplicaciones

1. Crea el administrador de Jellyfin. Añade una biblioteca de películas en `/data/library/movies` y otra de series en `/data/library/tv`. Si ya tienes películas, usa una carpeta por título, por ejemplo `/data/library/movies/Título (2026)/Título (2026).mp4`. Jellyfin tiene acceso de lectura y Bazarr de escritura para guardar los subtítulos junto al vídeo.
2. Entra en qBittorrent con el usuario `admin` y la contraseña temporal que muestra `docker compose logs qbittorrent`. Cambia la contraseña, elige `/data/torrents` como destino y crea las categorías `movies` y `tv` con destinos `/data/torrents/movies` y `/data/torrents/tv`. En las opciones avanzadas, selecciona la interfaz VPN `tun0` para el tráfico de BitTorrent. [Primer acceso a qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/)
3. En Radarr elige `/data/library/movies` como carpeta raíz y en Sonarr elige `/data/library/tv`. En ambos añade qBittorrent como cliente con servidor `gluetun`, puerto `8080` y la cuenta configurada. Asigna la categoría correspondiente y pulsa **Test**. Activa la importación de descargas completadas y los enlaces duros. Las rutas coinciden entre contenedores.
4. En Prowlarr añade tus indexadores y registra Radarr y Sonarr en **Settings → Apps**. Usa las direcciones internas de la tabla, incluida la de Prowlarr, y la clave API de cada aplicación. En Bazarr registra Radarr y Sonarr de la misma forma y elige los idiomas y proveedores de subtítulos.
5. Abre Seerr y conéctalo a Jellyfin usando su dirección interna y la cuenta administradora de Jellyfin. Selecciona las bibliotecas y configura Radarr y Sonarr como servidores predeterminados con sus claves API, perfil de calidad y carpetas raíz. Usa los nombres HTTPS privados para las URL que abrirá el navegador de un usuario.
6. Si quieres Jellyfin Enhanced, añade el repositorio indicado por el proyecto en el panel de complementos de Jellyfin, instala **Jellyfin Enhanced** desde el catálogo y reinicia Jellyfin. [Instalación del complemento](https://github.com/n00bcodr/Jellyfin-Enhanced#-install-in-a-minute)

## Comprobar el recorrido

Comprueba con `docker compose ps` que Gluetun indica `healthy` y consulta la IP de salida con `docker compose exec qbittorrent curl -fsS https://api.ipify.org`. Debe corresponder a tu VPN. Pide en Seerr un título disponible en uno de tus indexadores para el que tengas permiso de descarga. Comprueba que aparece en la cola de Radarr o Sonarr, que qBittorrent lo guarda bajo `/data/torrents` y que Jellyfin lo reproduce tras importar y escanear la biblioteca. En la VM, `stat -c '%d:%i %h %n' archivo_descargado archivo_importado` debe mostrar el mismo dispositivo e inodo si se ha creado un enlace duro.

Para una copia en frío, detén el proyecto con `docker compose stop`, copia a otro disco `MEDIA_CONFIG_DIR`, `MEDIA_DATA_DIR`, `.env` y tu perfil WireGuard si usas uno propio. Vuelve a arrancarlo con `docker compose up -d --wait`. Al restaurar, conserva los propietarios y los enlaces duros (por ejemplo con `rsync -aH` para el árbol de datos). Con VPNBook, vuelve a ejecutar `python3 scripts/vpnbook.py` antes del primer arranque.
