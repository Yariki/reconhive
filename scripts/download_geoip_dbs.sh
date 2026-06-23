#!/usr/bin/env bash
set -euo pipefail

: "${RECONHIVE_MAXMIND_ACCOUNT_ID:?Set RECONHIVE_MAXMIND_ACCOUNT_ID}"
: "${RECONHIVE_MAXMIND_LICENSE_KEY:?Set RECONHIVE_MAXMIND_LICENSE_KEY}"

output_dir="${RECONHIVE_GEOIP_DB_DIR:-data/geoip}"
tmpdir="$(mktemp -d)"
auth_file="${tmpdir}/netrc"

cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

mkdir -p "$output_dir"
printf 'machine download.maxmind.com\nlogin %s\npassword %s\n' \
  "$RECONHIVE_MAXMIND_ACCOUNT_ID" \
  "$RECONHIVE_MAXMIND_LICENSE_KEY" > "$auth_file"
chmod 600 "$auth_file"

download_mmdb() {
  local edition="$1"
  local target="$2"
  local archive="${tmpdir}/${edition}.tar.gz"
  local extracted

  curl -fsSL --retry 3 --location \
    --netrc-file "$auth_file" \
    "https://download.maxmind.com/geoip/databases/${edition}/download?suffix=tar.gz" \
    -o "$archive"

  tar -xzf "$archive" -C "$tmpdir"
  extracted="$(find "$tmpdir" -type f -name "$target" -print -quit)"
  if [[ -z "$extracted" ]]; then
    echo "Could not find ${target} in ${edition} archive" >&2
    return 1
  fi

  install -m 0644 "$extracted" "${output_dir}/${target}"
  echo "Wrote ${output_dir}/${target}"
}

download_mmdb "GeoLite2-City" "GeoLite2-City.mmdb"
download_mmdb "GeoLite2-ASN" "GeoLite2-ASN.mmdb"
