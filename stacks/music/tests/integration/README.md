# Comprobaciones de integración

Desde `stacks/music/` utiliza el Python del entorno de Armonía. Para localizar otro clon de la aplicación, define `ARMONIA_REPO` con su ruta.

| Comando | Qué comprueba |
| --- | --- |
| `python tests/integration/backend_actual.py` | Reserva atómica de trabajos por usuario, límite y caducidad de la caché e integridad de las respuestas HTTP parciales. Ejecuta pruebas de la versión presente en el clon. |
| `python tests/integration/deep_playlists_bench.py` | Índice de listas con 200 listas sintéticas de 500 pistas en una base SQLite temporal. Escribe las medidas en `runtime/mediciones/`. |
| `python -m pytest -q tests/` | Creación, autenticidad, restauración y retención de copias, bloqueo entre tareas, fixtures de audio y verificadores de restauración con transporte simulado. |

## Ensayo sobre una copia restaurada

Prepara un destino nuevo en `restores/`, con el nombre de proyecto, los montajes relativos y el puerto propios de ese clon. Arranca el clon con el mismo conjunto de usuarios. Las comprobaciones necesitan las cuentas y las integraciones previamente vinculadas que contiene la copia.

```sh
python tests/integration/verify_restore.py --target restores/ensayo --url http://127.0.0.1:19400
python tests/integration/deep_restore_snapshot.py antes --target restores/ensayo --url http://127.0.0.1:19400
python tests/integration/deep_restore_snapshot.py despues --target restores/ensayo --url http://127.0.0.1:19400 --compare runtime/mediciones/antes.json
```

Haz la segunda lectura sobre la misma restauración tras la operación que quieras comprobar. Las instantáneas guardan huellas de las cuentas, la música y la configuración. El directorio de destino debe contener el manifiesto de una restauración y el puerto debe ser distinto del de la instalación.
