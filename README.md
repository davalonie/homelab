# Homelab

Configuración del servidor doméstico por stacks. La entrada desde el navegador y el móvil se hace por HTTPS a través de Tailscale. En el stack de música, Tailscale Serve reenvía las peticiones al puerto 18400 de la interfaz de bucle local.

![Mapa del homelab con la entrada VPN, el almacenamiento y los grupos de servicios](Homelab%20completo.png)

| Stack | Contenido |
| --- | --- |
| [Música](stacks/music/README.md) | Compose, pruebas, copias y preparación de Armonía, Navidrome, Aurral y Koito. |
| [Media](stacks/media/README.md) | Plan de peticiones, adquisición, subtítulos y reproducción de vídeo. |
| [Immich](stacks/immich/README.md) | Plan de fototeca. |
| [Vaultwarden](stacks/vaultwarden/README.md) | Plan del gestor de contraseñas. |
| [Overleaf](stacks/overleaf/README.md) | Plan del editor LaTeX. |
| [Gestión](stacks/gestion/README.md) | Plan de administración, monitorización y almacenamiento compartido. |

Música incluye una configuración ejecutable. Los demás directorios documentan el alcance previsto. El repositorio hermano de Armonía contiene el código de la aplicación y sus herramientas de compilación. La guía de música explica cómo preparar el stack y obtener la API key de Last.fm. [Preparación de música y Last.fm](stacks/music/README.md#lastfm)

La documentación del servidor se organiza por [Proxmox](docs/proxmox.md), [acceso por Tailscale](docs/tailscale.md), [copias](docs/copias.md) y [discos](docs/discos.md). La configuración de este repositorio se distribuye bajo la [licencia MIT](LICENSE).
