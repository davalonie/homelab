# Distribución en Proxmox VE

El mapa de la raíz describe la arquitectura de referencia. Cada fila corresponde a un invitado independiente.

| Invitado | Función |
| --- | --- |
| LXC de Tailscale | Encaminamiento entre clientes autorizados y servicios privados mediante rutas de subred. |
| LXC de Pi-hole | Resolución DNS privada de los nombres de las aplicaciones hacia Caddy. |
| LXC de Caddy | Terminación HTTPS y proxy inverso hacia la aplicación que corresponda al nombre solicitado. |
| LXC no privilegiado de Authentik | Docker Compose para el proveedor de identidad y PostgreSQL. Prepara el soporte de Docker en este invitado. |
| VM Debian | Docker Engine y Compose para música y los demás stacks que se vayan incorporando. |

Configura el encaminamiento, DNS y TLS antes de habilitar el acceso remoto. Para integrar una aplicación compatible con OpenID Connect, registra en Authentik un cliente y su URI exacta de retorno, configura el emisor y las credenciales privadas en la aplicación y comprueba el acceso con una cuenta de prueba. La integración se habilita de forma independiente en cada aplicación.

Mantén en el inventario privado las asignaciones de red, identificadores de invitados, credenciales y destinos de copia. El repositorio incluye los Compose de música y media. Los demás stacks tienen documentación de planificación.
