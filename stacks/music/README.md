# Stack de música

Armonía sirve la web y la API. Navidrome gestiona las bibliotecas, Aurral las recomendaciones y Koito el historial de cada usuario. Compose publica únicamente Armonía en el puerto local 18400. El acceso del móvil se hace mediante el origen HTTPS privado de la instalación.

## Preparar música

Coloca los clones `armonia/` y `homelab/` en el mismo directorio. Desde `homelab/stacks/music/`, utiliza el entorno Python de Armonía para los scripts. Se necesitan Docker Compose, Python 3.12, `httpx` y `cryptography`. Configura `DOCKER_CONFIG` con la ruta al directorio privado de configuración de Docker.

1. Copia `.env.example` a `.env`. Ajusta `MUSIC_PUBLIC_ORIGIN` al origen HTTPS de tu instalación y revisa el UID y GID. `ARMONIA_BUILD_CONTEXT` admite otra ruta al directorio `middleware/`.
2. Ejecuta `python scripts/prepare.py` con el usuario que será propietario de los datos. Crea directorios, un catálogo inicialmente vacío y los archivos privados que falten. Conserva fuera del servidor una copia de `secrets/backup.key`.
3. Prepara Last.fm como se indica abajo. Elige los overlays y comprueba la configuración con `config --quiet`. La plantilla del móvil utiliza el catálogo normal y cookies seguras. El overlay de metadatos habilita la pasarela para Aurral.
4. En una instalación nueva, compila desde el clon hermano y arranca con los mismos archivos de Compose. Comprueba antes que el clon corresponde a la revisión de `versions.lock`. Si eliges otra revisión, actualiza `ARMONIA_COMMIT` en el entorno para que la etiqueta de revisión de la imagen identifique su origen.

```sh
export COMPOSE_FILE=compose.yaml:compose.phone.local.yaml:compose.metadata.yaml
docker --config "$DOCKER_CONFIG" compose config --quiet
docker --config "$DOCKER_CONFIG" compose build music
docker --config "$DOCKER_CONFIG" compose up -d
```

Con el stack operativo, aprovisiona una o dos cuentas con `python scripts/bootstrap.py --project music-homelab --users alice bob --docker-config "$DOCKER_CONFIG"`. Elige los nombres para tu instalación y conserva su orden si repites el comando. Para tres cuentas, activa primero el perfil `third-user`. Las contraseñas generadas quedan en `secrets/bootstrap-users.json`. Vincula cada cuenta de Aurral en la aplicación. Comprueba `/health` en el puerto local y abre el origen HTTPS desde el móvil.

## Last.fm

Crea una cuenta de Last.fm, inicia sesión, registra tu aplicación y copia el campo **API key**. La integración consulta los metadatos con esa clave. El **shared secret** se utiliza para llamadas firmadas y puedes dejarlo en Last.fm. [Registro de aplicaciones](https://www.last.fm/api/account/create) · [Consulta de artistas similares](https://www.last.fm/api/show/artist.getSimilar)

Guarda la API key en `secrets/lastfm-api.key`. Puedes introducirla sin eco ni argumentos de terminal con el comando siguiente, después de ejecutar `prepare.py`. Si vas a reutilizar la clave de una instalación anterior, copia directamente el archivo privado con permisos 600 en ese mismo destino. El overlay de metadatos lo monta en Aurral.

```sh
python -c 'from getpass import getpass; from pathlib import Path; p=Path("secrets/lastfm-api.key"); p.chmod(0o600); p.write_text(getpass("API key de Last.fm: ").strip()+"\n")'
```

## Audio y metadatos de prueba

Desde `stacks/music/` genera los datos antes de utilizar el overlay del laboratorio.

```sh
python3 tests/fixtures/prepare_audio.py
docker --config "$DOCKER_CONFIG" compose -f compose.yaml -f compose.lab.yaml config --quiet
docker --config "$DOCKER_CONFIG" compose -f compose.yaml -f compose.metadata-test.yaml config --quiet
```

El generador escribe `runtime/fixtures/one.wav`, `two.wav` y `sources.json`. Los archivos WAV son senoidales de 220 y 330 Hz. Cada uno tiene 34 segundos de PCM mono a 16 kHz y 16 bits. El catálogo contiene cuatro entradas que apuntan a esos dos archivos. Puedes volver a generarlos desde cualquier directorio invocando el script por su ruta.

| Overlay | Script y datos que utiliza |
| --- | --- |
| `compose.lab.yaml` | Monta `tests/fixtures/range_server.py` como programa de `fixtures`, y `runtime/fixtures/` en `/fixtures` para servir los WAV. Armonía lee el catálogo montado en `/app/fixtures/sources.json`. |
| `compose.metadata-test.yaml` | Monta `tests/fixtures/metadata.mjs` en Aurral y lo carga con Node para simular los metadatos externos. |

Los montajes son de solo lectura. Git conserva los tres scripts en `tests/fixtures/` y excluye el directorio `runtime/`.

## Operación

Las [instrucciones de copias y restauración](docs/MANTENIMIENTO.md), las [pruebas manuales](docs/PRUEBAS_MANUALES.md) y las [comprobaciones de integración](tests/integration/README.md) describen los procedimientos desde este directorio. Consulta también las [recomendaciones por usuario](docs/RECOMENDACIONES_PRIVADAS.md) y la [configuración de seguridad](docs/SEGURIDAD.md).
