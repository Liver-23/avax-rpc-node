# Avalanche full node - mainnet or Fuji via .env (AVAX_NETWORK)
FROM avaplatform/avalanchego:latest

USER root

RUN set -eux; \
    if command -v apk >/dev/null 2>&1; then \
      apk add --no-cache bash curl lz4 tar; \
    elif command -v apt-get >/dev/null 2>&1; then \
      apt-get update && apt-get install -y --no-install-recommends bash curl lz4 tar ca-certificates && rm -rf /var/lib/apt/lists/*; \
    else \
      echo "Unsupported base image: need apk or apt-get to install snapshot tools" >&2; exit 1; \
    fi

COPY scripts/entrypoint.sh /entrypoint.sh
COPY scripts/resolve-snapshot-url.sh /resolve-snapshot-url.sh
RUN chmod +x /entrypoint.sh /resolve-snapshot-url.sh

EXPOSE 9650 9651

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--http-host=0.0.0.0", "--system-tracker-disk-required-available-space-percentage=0"]
