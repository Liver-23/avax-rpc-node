# Avalanche full node - mainnet, JSON-RPC on 9650
# Wraps official image with default flags; data persisted via volume in compose
FROM avaplatform/avalanchego:latest

EXPOSE 9650 9651

# Bind inside container; host-level restriction is done in docker-compose port mapping
ENTRYPOINT ["/avalanchego/avalanchego"]
CMD ["--http-host=0.0.0.0"]
