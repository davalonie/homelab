# Vaultwarden

Vaultwarden guarda la bóveda, los adjuntos y su base SQLite en `VAULTWARDEN_DATA_DIR`. El Compose publica la web en `127.0.0.1:8222` y arranca con el registro y las invitaciones cerrados. [Proyecto Vaultwarden](https://github.com/dani-garcia/vaultwarden)

## Primer arranque

Desde `stacks/vaultwarden/` en la VM Debian, crea el archivo de configuración en la instalación nueva. Abre el registro solo para crear tu primera cuenta.

```bash
test -e .env || install -m 600 .env.example .env
VAULTWARDEN_SIGNUPS_ALLOWED=true docker compose up -d --wait
```

Desde tu equipo abre un túnel con `ssh -N -L 8222:127.0.0.1:8222 usuario@vm` y entra en `http://localhost:8222`. El navegador admite el cifrado del cliente en `localhost`. Crea la cuenta, guarda la contraseña maestra y vuelve a aplicar los valores de `.env` para cerrar el registro.

```bash
docker compose up -d --wait
curl -fsS http://127.0.0.1:8222/alive
```

Inicia sesión y crea una entrada de prueba. Para el acceso posterior por Caddy, `VAULTWARDEN_URL` debe coincidir con el origen HTTPS que usarán los clientes. [Configuración del registro](https://github.com/dani-garcia/vaultwarden/wiki/Disable-registration-of-new-users)

## Copia y recuperación

Detén el servicio con `docker compose stop`, copia todo `VAULTWARDEN_DATA_DIR` y `.env` a un destino cifrado en otro disco y vuelve a arrancar con `docker compose up -d --wait`. El directorio completo conserva también las claves y los adjuntos. Para probar la recuperación, restaura esa copia en un directorio vacío con la misma versión y propietarios, arranca el stack y comprueba que puedes abrir una entrada y descargar un adjunto. [Copias de Vaultwarden](https://github.com/dani-garcia/vaultwarden/wiki/Backing-up-your-vault)
