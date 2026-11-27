# Stack de música

Armonía sirve la web y la API. Navidrome gestiona las bibliotecas, Aurral las recomendaciones y Koito el historial de cada usuario. Compose publica únicamente Armonía en el puerto local 18400. El acceso del móvil se hace mediante el origen HTTPS privado de la instalación.

## Preparar música

En la VM Debian necesitas Docker Engine, Compose v2 y Python 3.12 con `httpx` y `cryptography` (por ejemplo en un entorno virtual). La imagen publicada de Armonía 0.8.0 es para Linux amd64. El usuario de aprovisionamiento necesita acceso al motor Docker local y a las redes de los contenedores desde la VM. Ejecuta estos pasos desde `stacks/music/`.

1. Crea el entorno privado con `install -m 600 .env.example .env` en una instalación nueva. Ajusta `MUSIC_UID` y `MUSIC_GID` a los de la cuenta sin privilegios que ejecutará los scripts. Usa `MUSIC_RUNTIME_DIR=./runtime` o una ruta absoluta dedicada fuera del repositorio, en un disco montado y escribible por esa cuenta. Las variables exportadas en la sesión prevalecen sobre el archivo.
2. Define `MUSIC_PUBLIC_ORIGIN`, `MUSIC_BIND` y `MUSIC_PORT` según el [procedimiento de DNS privado y Caddy](../../docs/tailscale.md). Prepara el acceso al backend desde la red del proxy.
3. Ejecuta `python scripts/prepare.py`. Los datos quedan en el runtime. Los secretos y el catálogo siguen en `secrets/` y `config/` del proyecto. La preparación conserva los archivos existentes. Custodia una copia separada de `secrets/backup.key`.
4. Elige los overlays antes de arrancar. El base sirve para producción. Para el cliente móvil puedes añadir `compose.phone.local.yaml`. Si habilitas la pasarela de metadatos, prepara primero la clave de Last.fm y añade `compose.metadata.yaml`. Mantén la selección en `COMPOSE_FILE` del `.env` local (en Linux se separan los nombres con `:`).

```sh
docker compose config --quiet
docker compose pull
docker compose up -d --wait
python scripts/bootstrap.py --project music-homelab --users user-a user-b
```

Sustituye los nombres de ejemplo durante el aprovisionamiento. Cada posición corresponde a una instancia de Koito con SQLite, red y credenciales propias. Los identificadores internos `alice`, `bob` y `carol` conservan los montajes y las integraciones existentes. Puedes empezar con una cuenta y repetir el comando con otra al final. Para la tercera, define `COMPOSE_PROFILES=third-user`, ejecuta `docker compose up -d --wait` y añade su nombre al final de la lista. El script conserva las contraseñas en `secrets/bootstrap-users.json` y rechaza cambiar el orden de cuentas ya asignadas. Armonía vincula Aurral al iniciar sesión.

## Imagen y desarrollo

Compose usa por defecto la misma referencia por versión y digest de `versions.lock`. Deja `MUSIC_IMAGE` vacío para seguir esa selección. En un despliegue anterior revisa el `.env` local y retira la referencia a la imagen compilada de 0.7.0 cuando estés listo para actualizar. [Paquete de Armonía en GHCR](https://github.com/davalonie/armonia/pkgs/container/armonia)

Para desarrollo, clona Armonía y selecciona la revisión de `armonia.source` de `versions.lock`. El overlay usa `../../../armonia/middleware` como contexto y crea la imagen local `armonia:dev`. Puedes ajustar `ARMONIA_BUILD_CONTEXT`, `ARMONIA_COMMIT` y `MUSIC_APP_NAME`. Desde una instalación de desarrollo con sus propios datos:

```sh
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
```

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
docker compose -f compose.yaml -f compose.lab.yaml config --quiet
docker compose -f compose.yaml -f compose.metadata-test.yaml config --quiet
```

Las rutas siguientes usan el runtime predeterminado. El generador escribe `runtime/fixtures/one.wav`, `two.wav` y `sources.json`. Los archivos WAV son senoidales de 220 y 330 Hz. Cada uno tiene 34 segundos de PCM mono a 16 kHz y 16 bits. El catálogo contiene cuatro entradas que apuntan a esos dos archivos. Puedes volver a generarlos desde cualquier directorio invocando el script por su ruta.

| Overlay | Script y datos que utiliza |
| --- | --- |
| `compose.lab.yaml` | Monta `tests/fixtures/range_server.py` como programa de `fixtures`, y `runtime/fixtures/` en `/fixtures` para servir los WAV. Armonía lee el catálogo montado en `/app/fixtures/sources.json`. |
| `compose.metadata-test.yaml` | Monta `tests/fixtures/metadata.mjs` en Aurral y lo carga con Node para simular los metadatos externos. |

Los montajes son de solo lectura. Git conserva los tres scripts en `tests/fixtures/` y excluye el directorio `runtime/`.

## Operación

Las [instrucciones de copias y restauración](docs/MANTENIMIENTO.md), las [pruebas manuales](docs/PRUEBAS_MANUALES.md) y las [comprobaciones de integración](tests/integration/README.md) describen los procedimientos desde este directorio. Consulta también las [recomendaciones por usuario](docs/RECOMENDACIONES_PRIVADAS.md) y la [configuración de seguridad](docs/SEGURIDAD.md).
