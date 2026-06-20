#!/bin/bash
set -euo pipefail

DATA_DIR="/root/.avalanchego"
NETWORK="${AVAX_NETWORK:-mainnet}"
SNAPSHOT_RESTORE="${SNAPSHOT_RESTORE:-true}"
RESOLVE_SNAPSHOT_URL="/resolve-snapshot-url.sh"

is_data_empty() {
  if [ ! -d "$DATA_DIR/db" ]; then
    return 0
  fi
  if [ -z "$(find "$DATA_DIR/db" -mindepth 1 -print -quit 2>/dev/null)" ]; then
    return 0
  fi
  return 1
}

resolve_snapshot_url() {
  if [ -n "${SNAPSHOT_URL:-}" ]; then
    printf '%s\n' "$SNAPSHOT_URL"
    return 0
  fi
  "$RESOLVE_SNAPSHOT_URL" "$NETWORK"
}

restore_snapshot() {
  url="$(resolve_snapshot_url)"
  extract_dir="${SNAPSHOT_EXTRACT_DIR:-$DATA_DIR/db}"

  echo "Data directory is empty; restoring snapshot from:"
  echo "  $url"
  echo "Streaming download | lz4 -dc | tar -xf - into ${extract_dir}"
  mkdir -p "$extract_dir"

  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --retry-delay 5 "$url" | lz4 -dc | tar -xf - -C "$extract_dir"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- "$url" | lz4 -dc | tar -xf - -C "$extract_dir"
  else
    echo "ERROR: curl or wget is required for snapshot restore" >&2
    exit 1
  fi

  echo "Snapshot restore complete."
}

extra_args=""
case "$NETWORK" in
  fuji|testnet|avaxt)
    extra_args="--network-id=fuji"
    ;;
esac

if is_data_empty; then
  if [ "$SNAPSHOT_RESTORE" = "true" ] || [ "$SNAPSHOT_RESTORE" = "1" ] || [ "$SNAPSHOT_RESTORE" = "yes" ]; then
    restore_snapshot
  else
    echo "Data directory is empty and SNAPSHOT_RESTORE is disabled; starting sync from scratch."
  fi
else
  echo "Using existing chain data in $DATA_DIR/db"
fi

exec /avalanchego/build/avalanchego "$@" $extra_args
