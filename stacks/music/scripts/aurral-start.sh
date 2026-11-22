#!/bin/sh
set -eu
umask 077
# Upstream 2.13.0 has no *_FILE for these variables. Do not echo them.
AUTH_PASSWORD=$(cat /run/secrets/aurral_admin_password)
AURRAL_API_KEY=$(cat /run/secrets/aurral_api_key)
export AUTH_PASSWORD AURRAL_API_KEY
if [ "${MUSIC_METADATA_PROXY_ENABLED:-false}" = true ]; then
  proxy_key=$(cat /run/secrets/metadata_proxy_key)
  LASTFM_API_KEY=$(cat /run/secrets/lastfm_api_key)
  if [ -z "$LASTFM_API_KEY" ]; then
    echo 'Metadata is enabled but the Last.fm API key file is empty.' >&2
    exit 1
  fi
  HTTPS_PROXY="http://aurral:${proxy_key}@music:8002"
  HTTP_PROXY="$HTTPS_PROXY"
  export HTTPS_PROXY HTTP_PROXY LASTFM_API_KEY
  unset LASTFM_API_SECRET
fi
exec node --max-semi-space-size=4 backend/server.ts
