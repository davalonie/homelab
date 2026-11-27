# Acceso opcional con Authentik

El Compose base admite el acceso individual con usuario y contraseña de Navidrome. El overlay añade OIDC a la misma aplicación web y Android. Cada identidad se vincula a una cuenta musical ya aprovisionada y conserva sus bibliotecas, su cuenta de Aurral y la instancia de Koito que le corresponde.

## Preparar el proveedor

1. En Authentik crea la aplicación y un proveedor OAuth2/OpenID con cliente confidencial, flujo Authorization Code, emisor por aplicación y firma RS256. Para una instalación nueva usa **User UUID** como modo de sujeto. Conserva ese modo al actualizar o restaurar el proveedor.
2. Selecciona los mappings `openid` y `profile`. Vincula a la aplicación el grupo que puede entrar. Si configuras `MUSIC_OIDC_GROUP`, incluye en el ID token el claim `groups` como lista de nombres.
3. Registra como redirección **estricta** el origen HTTPS de Armonía seguido de `/api/oidc/callback`, por ejemplo `https://music.example.org/api/oidc/callback`. Ese callback sirve a ambos clientes. Caddy debe conservar el encabezado Host del sitio. Tanto el cliente como el contenedor `music` deben poder resolver el emisor por DNS, alcanzarlo por HTTPS y confiar en su certificado.

## Activar en el stack

Desde `stacks/music/`, configura en el `.env` privado las variables documentadas en [.env.example](../.env.example).

| Variable | Valor de la instalación |
| --- | --- |
| `MUSIC_PUBLIC_ORIGIN` | Origen HTTPS de Armonía, sin ruta. |
| `MUSIC_OIDC_ISSUER` | Valor exacto de `issuer` en el documento de discovery, incluida la barra final cuando corresponda. |
| `MUSIC_OIDC_CLIENT_ID` | ID del cliente confidencial registrado en Authentik. |
| `MUSIC_OIDC_GROUP` | Grupo que Armonía exige en el ID token. Vacío deja la autorización por grupo en manos de Authentik. |
| `MUSIC_LIBRARY_SUBNET` | Subred IPv4 para la red Docker interna `library`. Elige una que no se solape con otras redes Docker ni rutas de la VM o de Tailscale. |
| `MUSIC_LIBRARY_IP_RANGE` | Bloque CIDR dentro de esa subred para las asignaciones dinámicas de Docker. |
| `MUSIC_PROXY_IP` | IPv4 fija del contenedor **music** en esa subred, fuera del bloque dinámico y distinta de la puerta de enlace. Navidrome solo acepta `X-Armonia-User` desde esta dirección /32. Caddy sigue comunicándose exclusivamente con Armonía. |

Ejecuta `prepare.py` como indica el README del stack. Con ese mismo usuario, copia el archivo privado que contiene el secreto emitido por Authentik. Define `ARCHIVO_SECRETO_OIDC` con su ruta. El archivo debe contener únicamente el valor del secreto.

```sh
install -m 600 -- "$ARCHIVO_SECRETO_OIDC" secrets/oidc-client-secret
```

El overlay monta ese archivo en `/run/secrets/oidc_client_secret` solo en Armonía. Si rotas el secreto en Authentik, actualiza el archivo y recrea el contenedor con `docker compose up -d --force-recreate music`.

Si el stack ya está en marcha, programa una breve parada para recrear la red `library`. Con los overlays actuales, ejecuta `docker compose --profile third-user down`. Los bind mounts conservan los datos. Después añade `compose.authentik.yaml` a `COMPOSE_FILE` en el `.env`. Para OIDC solo, usa `compose.yaml:compose.authentik.yaml`. Una instalación que también utiliza móvil y metadatos puede usar:

```dotenv
COMPOSE_FILE=compose.yaml:compose.phone.local.yaml:compose.metadata.yaml:compose.authentik.yaml
```

Valida con `docker compose config --quiet` y arranca con `docker compose up -d --wait`. En el origen HTTPS, `/api/oidc/config` debe devolver `{"enabled":true}`. Para volver al acceso tradicional, repite la parada con la selección activa, retira el overlay OIDC y arranca con la selección anterior. Los vínculos quedan en la base de datos para una futura activación.

## Vincular una cuenta musical

Aprovisiona primero la cuenta siguiendo el README. Verifica en Authentik el sujeto estable del usuario (campo `uuid` si elegiste **User UUID**). Obtén el ID nativo de esa misma cuenta en Navidrome o el `userId` de `/api/me` tras entrar con su contraseña local. Con ambos registros comprobados, ejecuta en una terminal privada:

```sh
docker compose exec music python -m tools.bind_oidc \
  --subject "$AUTHENTIK_SUBJECT" \
  --user-id "$NAVIDROME_USER_ID" --username "$MUSIC_USERNAME"
```

Las tres variables del comando representan los valores que acabas de verificar. La herramienta pide la contraseña de esa cuenta sin eco, comprueba su ID con Navidrome y guarda el vínculo entre emisor, sujeto e ID musical. Repite el proceso por persona y vuelve a ejecutarlo si cambia la contraseña de Navidrome. Un sujeto sin vínculo no obtiene sesión musical. Aurral usa la cuenta asignada durante el aprovisionamiento. Si tiene una contraseña propia, vincúlala en **Ajustes → Recomendaciones**.

## Comprobar web y Android

- **Web.** Abre el origen HTTPS y selecciona **Entrar con Authentik**. Al regresar, comprueba la biblioteca, las recomendaciones y el historial con dos cuentas distintas. Comprueba también el acceso tradicional y el rechazo de una identidad sin vínculo.
- **Android.** Configura el mismo origen HTTPS en la app. El navegador externo completa el login y vuelve a la app mediante un código de un solo uso. En Authentik se registra únicamente el callback HTTPS del servidor. Para una compilación con ID personalizado, configura `MUSIC_ANDROID_APPLICATION_ID` con el mismo ID base usado al compilar.
- **Grupo.** Si exiges un grupo, prueba también con una cuenta sin ese permiso. Para alternar entre identidades durante el ensayo, cambia de usuario en Authentik, que mantiene su propia sesión de navegador.

[Documentación de Armonía 0.8.0](https://github.com/davalonie/armonia/blob/v0.8.0/docs/authentik.md) · [Copias y restauración del stack](MANTENIMIENTO.md#recuperar-una-instalación-con-oidc)
