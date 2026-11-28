# Homelab

Proxmox VE aloja cuatro LXC independientes para Tailscale (subnet router), Pi-hole, Caddy y Authentik. Authentik utiliza Docker Compose en un LXC no privilegiado. Una VM Debian ejecuta los stacks principales de Compose.

Los clientes consultan el DNS privado y llegan por Tailscale a Caddy, que termina HTTPS y reenvía cada petición al backend correspondiente. El mapa representa la arquitectura objetivo. La integración de Authentik mediante OpenID Connect se habilita progresivamente en las aplicaciones compatibles.

![Mapa del homelab con la entrada VPN, el almacenamiento y los grupos de servicios](Homelab%20completo.png)

| Stack | Contenido |
| --- | --- |
| [Música](stacks/music/README.md) | Compose, pruebas, copias y preparación de Armonía, Navidrome, Aurral y Koito. |
| [Media](stacks/media/README.md) | Compose para peticiones con Seerr, descargas por VPN, subtítulos y reproducción en Jellyfin. |
| [Immich](stacks/immich/README.md) | Fototeca, aprendizaje automático y almacenamiento de originales. |
| [Vaultwarden](stacks/vaultwarden/README.md) | Gestor de contraseñas con SQLite y registro privado. |
| [Overleaf CE+](stacks/overleaf/README.md) | Editor LaTeX colaborativo con MongoDB y Redis. |
| [Gestión](stacks/gestion/README.md) | Plan de administración, monitorización y almacenamiento compartido. |

Cada stack de aplicaciones incluye su Compose y una guía de arranque. Gestión sigue en planificación. El stack de Música descarga la imagen publicada de Armonía en GHCR. La guía explica el aprovisionamiento y los metadatos opcionales de Last.fm. [Preparación de música y Last.fm](stacks/music/README.md#lastfm)

La documentación del servidor se organiza por [Proxmox](docs/proxmox.md), [acceso por Tailscale](docs/tailscale.md), [copias](docs/copias.md) y [discos](docs/discos.md). La configuración de este repositorio se distribuye bajo la [licencia MIT](LICENSE).
