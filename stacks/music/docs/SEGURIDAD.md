# Seguridad del stack de música

El punto de entrada publicado por defecto es `127.0.0.1:18400`. Navidrome, Aurral y Koito permanecen en redes internas. Para el móvil usa HTTPS privado y el origen exacto configurado en Armonía. Las credenciales de sesión y de integración son propias de cada instalación.

Conserva `secrets/` con permisos de directorio 700 y sus archivos con 600. Asigna los directorios de datos al UID y GID que utiliza Compose. Revisa que el perfil y los montajes efectivos corresponden al uso previsto. Las fuentes HTTP y los servicios ficticios pertenecen al laboratorio.

Mantén fuera de Git el entorno local, las grabaciones, las bases de datos, las copias y las claves de firma o recuperación. Para comprobar la configuración sin volcar el entorno usa `docker compose config --quiet`.
