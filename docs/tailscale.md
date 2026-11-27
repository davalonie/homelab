# Acceso privado por HTTPS

1. Habilita el reenvío en el LXC de Tailscale. Anuncia y aprueba la ruta de subred necesaria. Limita el acceso de los clientes autorizados al DNS privado y al HTTPS de Caddy.
2. Configura Pi-hole como resolutor para la zona privada de los clientes. El nombre de cada aplicación debe resolver a la dirección de Caddy alcanzable por esa ruta.
3. En la VM, configura `MUSIC_BIND` con la dirección privada a la que conecta Caddy y `MUSIC_PORT` con el puerto del backend. El valor inicial de bucle local sirve para pruebas en la propia VM. Limita el acceso al puerto publicado al LXC de Caddy mediante reglas efectivas sobre tráfico de Docker o el cortafuegos de Proxmox.
4. En Caddy configura el nombre del sitio, su certificado y el backend. El ejemplo usa variables del entorno del LXC. `MUSIC_HOST` contiene solo el nombre y `MUSIC_UPSTREAM` la dirección privada de la VM con su puerto. Para certificados públicos mediante ACME DNS-01 configura el módulo DNS y su credencial en el LXC. También puedes cargar certificados gestionados por tu instalación.

```caddyfile
{$MUSIC_HOST} {
    tls {$MUSIC_CERT_FILE} {$MUSIC_KEY_FILE}
    reverse_proxy {$MUSIC_UPSTREAM}
}
```

5. En el stack usa el origen HTTPS exacto en `MUSIC_PUBLIC_ORIGIN`, por ejemplo `https://music.example.org`, y conserva las cookies seguras. Desde un cliente autorizado comprueba la resolución DNS, la confianza del certificado, `/health` y el inicio de sesión. Comprueba desde otro equipo que el puerto directo de la VM queda restringido.

Tailscale proporciona la ruta de red. Caddy atiende HTTPS para las aplicaciones. La publicación de un servicio requiere su propia configuración DNS y de proxy.
