# Acceso por Tailscale

El cliente entra en la red privada e inicia HTTPS contra el origen configurado para el servicio. En el nodo de música, Tailscale Serve entrega el tráfico a `127.0.0.1:18400`. El overlay del móvil espera el mismo origen HTTPS en `MUSIC_PUBLIC_ORIGIN`. Los demás componentes del stack se comunican por sus redes internas de Compose.

Tras configurar el acceso, comprueba el destino con `tailscale serve status` en el equipo y abre la web desde un cliente autorizado. El resultado del comando puede identificar la red privada. Por hacer: documentar las reglas de acceso de los demás stacks.
