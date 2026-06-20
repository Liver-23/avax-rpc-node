#!/bin/sh
set -eu

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
  tmpdir=""
  tmpdir="$(mktemp -d)"
  archive="${tmpdir}/snapshot.tar.lz4"
  tarball="${tmpdir}/snapshot.tar"

  cleanup() {
    rm -rf "$tmpdir"
  }
  trap cleanup EXIT

  echo "Data directory is empty; restoring snapshot from:"
  echo "  $url"
  mkdir -p "$DATA_DIR"

  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 --retry-delay 5 --progress-bar "$url" -o "$archive"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$archive" "$url"
  else
    echo "ERROR: curl or wget is required for snapshot restore" >&2
    exit 1
  fi

  lz4 -d "$archive" "$tarball"

  first="$(tar -tf "$tarball" | head -1)"
  case "$first" in
    .avalanchego/*|.avalanchego)
      tar -xf "$tarball" -C /root
      ;;
    ./db/*|./chainData/*|db/*|chainData/*)
      tar -xf "$tarball" -C "$DATA_DIR" --strip-components=1
      ;;
    *)
      tar -xf "$tarball" -C "$DATA_DIR"
      ;;
  esac

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

exec /avalanchego/avalanchego "$@" $extra_args
