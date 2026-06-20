#!/bin/sh
# Resolve the latest PublicNode pruned snapshot URL for Avalanche mainnet or Fuji.
# URLs change frequently; see https://publicnode.com/snapshots
set -eu

NETWORK="${1:-mainnet}"
VARIANT="${SNAPSHOT_VARIANT:-pruned}"
PAGE_URL="${SNAPSHOT_INDEX_URL:-https://publicnode.com/snapshots}"

page="$(curl -fsSL "$PAGE_URL")"

case "$NETWORK" in
  fuji|testnet|avaxt)
    prefix="avalanche-fuji-${VARIANT}-"
    ;;
  *)
    prefix="avalanche-${VARIANT}-"
    ;;
esac

# Pick the URL with the highest block height suffix.
url="$(
  printf '%s' "$page" \
    | grep -oE "https://snapshots\\.publicnode\\.com/${prefix}[0-9]+\\.tar\\.lz4" \
    | awk -F'-' '{ block=$NF; sub(/\.tar\.lz4$/, "", block); print block, $0 }' \
    | sort -k1,1nr \
    | head -1 \
    | awk '{ print $2 }'
)"

if [ -z "$url" ]; then
  echo "ERROR: Could not find ${prefix}*.tar.lz4 on ${PAGE_URL}" >&2
  echo "Set SNAPSHOT_URL manually or check https://publicnode.com/snapshots" >&2
  exit 1
fi

printf '%s\n' "$url"
