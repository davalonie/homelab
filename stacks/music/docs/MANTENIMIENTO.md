# Mantenimiento de música

Ejecuta los comandos desde `stacks/music/`, con un Python que disponga de `cryptography`. Revisa `versions.lock` al actualizar componentes y prueba la nueva versión sobre una restauración independiente.

## Copia completa

Guarda una copia externa de `secrets/backup.key`. La herramienta cifra el archivo con AES-GCM y excluye la propia clave. Elige un archivo nuevo en el disco de copias. Guarda también por separado las configuraciones privadas de infraestructura y los overlays propios que hayas añadido. Durante la captura se detienen los servicios en marcha del proyecto seleccionado y después se arrancan esos mismos servicios.

```sh
python scripts/backup.py create "$DESTINO/musica-completa.agcm" --project music-homelab
python scripts/backup.py restore "$DESTINO/musica-completa.agcm" --key "$CLAVE_RECUPERACION" --target restores/ensayo
```

La restauración exige un destino nuevo, autentica el archivo antes de extraer y acaba con los servicios parados. Usa un nombre de proyecto y un puerto de bucle local exclusivos si arrancas el clon. La copia utiliza la ruta lógica `runtime/` incluso cuando los datos proceden de otro disco. El restaurador actual fija `MUSIC_RUNTIME_DIR=./runtime` en el entorno recuperado. Antes de arrancar el clon, limpia las variables exportadas que pudieran apuntar a producción y revisa el proyecto, el bind, el puerto, el origen y los overlays en su propio `.env`. Comprueba los montajes efectivos con `docker compose config` en una consola privada. Si recuperas una copia programada, coloca el espejo en `runtime/music/` y ejecuta `prepare.py` como propietario para crear los directorios vacíos. Para continuar con la misma clave de copia, reinstálala con permisos 600 antes de preparar.

## Copia programada

```sh
python scripts/scheduled_backup.py run --dest "$DESTINO" --keep 14
python scripts/scheduled_backup.py verify "$ARCHIVO_DE_ESTADO" --key "$CLAVE_RECUPERACION"
```

El destino debe estar montado en otro disco. El estado se conserva cifrado bajo `estado/` y la música se copia como archivos bajo `musica/`. El espejo conserva los archivos que desaparecen del origen. La retención se aplica a las copias de estado. Las instantáneas SQLite son coherentes por base de datos. Para una captura conjunta con todos los escritores parados utiliza la copia completa.

Las plantillas de [systemd](../scripts/systemd/) programan la copia a las 04:30, con hasta 15 minutos de margen. Para instalarlas como usuario, copia el servicio y el temporizador a `~/.config/systemd/user/` y la plantilla de entorno a `~/.config/armonia-copia.env`. Ajusta destino, ruta del stack y Python. Si eliges incluir la firma Android, indica su archivo privado en `ARMONIA_FIRMA`; para omitirlo, deja esa variable vacía. Tras revisar los valores, ejecuta `systemctl --user daemon-reload` y `systemctl --user enable --now armonia-copia.timer`.

## Recuperar una instalación con OIDC

La copia completa y el estado cifrado de la programada incluyen `compose.authentik.yaml`, el `.env` local, `secrets/oidc-client-secret`, `secrets/credential.key` y la base `runtime/music-app/armonia.db`. Restaura la base junto con esa clave para conservar los vínculos y poder descifrar las credenciales individuales. Las asignaciones de Aurral y los tokens de Koito se recuperan con el resto de `secrets/`.

Respalda Authentik en su propio LXC. Para recuperar el acceso con los vínculos originales, conserva allí el emisor y los sujetos de los usuarios y revisa el cliente, el secreto vigente y la URI de retorno. Si ensayas en paralelo, configura subredes Docker libres y un cliente y callback de prueba, o arranca el clon con autenticación tradicional. Antes de dar por recuperado OIDC, verifica el acceso de una cuenta vinculada y sus bibliotecas e historial. [Guía de Authentik](AUTHENTIK.md)

## Trasladar el runtime

1. Comprueba el montaje y el espacio del destino con `findmnt -T` y `df -h`. Usa un directorio nuevo, vacío y dedicado fuera del repositorio. Configura el arranque de la VM para que el disco esté montado antes de iniciar Docker.
2. Haz una copia completa, suspende el temporizador de copias si está activo y detén todos los escritores, incluido el tercer Koito si existe. Usa el mismo proyecto y overlays con `docker compose --profile third-user stop`.
3. Define en la consola `ORIGEN` y `DESTINO` con las rutas absolutas de los directorios de datos. Copia todo el árbol con `rsync -aHAX --numeric-ids "$ORIGEN/" "$DESTINO/"`, con permisos suficientes para preservar propietarios. Repite con `rsync -aHAXnci --numeric-ids "$ORIGEN/" "$DESTINO/"` y comprueba que no lista diferencias.
4. Cambia solo `MUSIC_RUNTIME_DIR` en el `.env`, elimina cualquier valor exportado anterior y comprueba los bind mounts. Arranca con `docker compose up -d --wait`. Comprueba reproducción, bibliotecas, historial por cuenta y una copia desde la ruta nueva antes de reactivar la programación. Conserva el origen para poder volver a él con los servicios detenidos. Si ya hubo escrituras en el destino, sincronízalas antes de volver.

## Actualizar imágenes

Haz una copia y ensaya primero con una restauración. Comprueba en el registro la etiqueta, plataforma, digest y revisión de la nueva imagen. Actualiza juntos el Compose y `versions.lock` y revisa cualquier override local de `MUSIC_IMAGE`. Usa `docker compose pull` y `docker compose up -d --wait` con los mismos perfiles y overlays. Prueba el acceso por HTTPS y dos cuentas independientes. Si una actualización migró las bases de datos, vuelve a la versión anterior junto con su copia previa.
