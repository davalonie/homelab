# Mantenimiento de música

Ejecuta los comandos desde `stacks/music/`, con un Python que disponga de `cryptography`. El directorio que indica `DOCKER_CONFIG` debe ser el de tu instalación. Revisa `versions.lock` al actualizar componentes y prueba la nueva versión sobre una restauración independiente.

## Copia completa

Guarda una copia externa de `secrets/backup.key`. La herramienta cifra el archivo con AES-GCM y excluye la propia clave. Elige un archivo nuevo en el disco de copias. Durante la captura se detienen los servicios en marcha del proyecto seleccionado y después se arrancan esos mismos servicios.

```sh
python scripts/backup.py create "$DESTINO/musica-completa.agcm" --project music-homelab --docker-config "$DOCKER_CONFIG"
python scripts/backup.py restore "$DESTINO/musica-completa.agcm" --key "$CLAVE_RECUPERACION" --target restores/ensayo
```

La restauración exige un destino nuevo, autentica el archivo antes de extraer y acaba con los servicios parados. Usa un nombre de proyecto y un puerto de bucle local exclusivos si arrancas el clon. Revisa también sus rutas de compilación.

## Copia programada

```sh
python scripts/scheduled_backup.py run --dest "$DESTINO" --keep 14
python scripts/scheduled_backup.py verify "$ARCHIVO_DE_ESTADO" --key "$CLAVE_RECUPERACION"
```

El destino debe estar montado en otro disco. El estado se conserva cifrado bajo `estado/` y la música se copia como archivos bajo `musica/`. El espejo conserva los archivos que desaparecen del origen. La retención se aplica a las copias de estado. Para reconstruir una biblioteca desde esta modalidad, restaura el archivo de estado con `backup.py restore` y recupera la música del espejo que corresponda. Las instantáneas SQLite son coherentes por base de datos. Para una captura conjunta con todos los escritores parados utiliza la copia completa.

Las plantillas de [systemd](../scripts/systemd/) programan la copia a las 04:30, con hasta 15 minutos de margen. Para instalarlas como usuario, copia el servicio y el temporizador a `~/.config/systemd/user/` y la plantilla de entorno a `~/.config/armonia-copia.env`. Ajusta destino, ruta del stack y Python. Si eliges incluir la firma Android, indica su archivo privado en `ARMONIA_FIRMA`; para omitirlo, deja esa variable vacía. Tras revisar los valores, ejecuta `systemctl --user daemon-reload` y `systemctl --user enable --now armonia-copia.timer`.
