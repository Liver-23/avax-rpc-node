# Multi-Chain Mainnet RPC Nodes

Full-node (non-archive) RPC services for BTC, BCH, XLM, TRX, AVAX, and SONIC. Each chain runs via **Docker** or **systemd** as specified below.

All paths are relative to **`/home/mainnet`** unless otherwise noted.

---

## Quick reference

| Chain | Runtime | API type | Port(s) | Start command |
|-------|---------|----------|---------|----------------|
| **BTC** | Docker | JSON-RPC | 8332 (RPC), 8333 (P2P) | `docker compose -f /home/mainnet/btc/docker-compose.yml up -d` |
| **BCH** | Docker | JSON-RPC | 8432 (RPC), 8334→8333 (P2P) | `docker compose -f /home/mainnet/bch/docker-compose.yml up -d` |
| **XLM** | Docker | REST + JSON-RPC | 8000 (Horizon), 8001 (Stellar RPC) | `docker compose -f /home/mainnet/xlm/docker-compose.yml up -d` |
| **TRX** | Docker | REST | 8090, 8091 | `docker compose -f /home/mainnet/trx/docker-compose.yml up -d` |
| **AVAX** | Docker | JSON-RPC | 9650 (RPC), 9651 (P2P) | `docker compose -f /home/mainnet/avax/docker-compose.yml up -d` |
| **SONIC** | systemd | JSON-RPC | 8899 | `sudo systemctl start mainnet-sonic-rpc` |

---

## Prerequisites

- **Docker** and **Docker Compose** (v2) for BTC, BCH, XLM, TRX, AVAX.
- **SONIC**: Install Sonic validator binaries on the host, apply sysctl and file limits from [Sonic docs](https://docs.sonic.game/architecture/hypergrid-framework/operator-guides/deploying-a-sonic-rpc-node), then install the systemd unit (see [sonic/README.md](../sonic/README.md)).

---

## Per-chain summary

### BTC (Bitcoin Core)
- **Config**: `btc/bitcoin.conf` — set `rpcuser`/`rpcpassword` and optionally `rpcallowip`.
- **Endpoints**: `http://<host>:8332` (JSON-RPC).
- **Install**: Image `bitcoin/bitcoin` from Docker Hub.

### BCH (Bitcoin Cash Node)
- **Config**: `bch/bitcoin.conf` — set `rpcuser`/`rpcpassword` and optionally `rpcallowip`.
- **Endpoints**: `http://<host>:8432` (JSON-RPC).
- **Install**: Image `uphold/bitcoin-cash-node` from Docker Hub.

### XLM (Stellar)
- **Stack**: stellar-core + Horizon (REST) + Stellar RPC (JSON-RPC). Postgres and init script in `xlm/`.
- **Config**: `xlm/stellar-core.cfg`, `xlm/horizon.env`, `xlm/stellar-rpc.conf`.
- **Endpoints**: `http://<host>:8000` (Horizon REST), `http://<host>:8001` (Stellar RPC JSON-RPC).
- **Install**: Images `stellar/stellar-core`, `stellar/stellar-horizon`, `stellar/soroban-rpc`, `postgres:15-alpine`.

### TRX (Tron)
- **Config**: `trx/config.conf`; optional full config from [java-tron](https://github.com/tronprotocol/java-tron/blob/develop/framework/src/main/resources/config.conf).
- **Endpoints**: `http://<host>:8090` (REST).
- **Install**: Image `tronprotocol/java-tron` from Docker Hub. FullNode.jar is included in the image.

### AVAX (Avalanche)
- **Config**: Optional flags in `avax/docker-compose.yml` under `command`.
- **Endpoints**: `http://<host>:9650` (JSON-RPC).
- **Install**: Image `avaplatform/avalanchego` from Docker Hub.

### SONIC
- **Config**: `sonic/start_node.sh` (set `PUBLIC_IP`, `VALIDATOR_ID`, `VALIDATOR_GENESIS_HASH` for mainnet); `sonic/config/` for validator keypair.
- **Endpoints**: `http://<host>:8899` (JSON-RPC).
- **Install**: Follow [sonic/README.md](../sonic/README.md); install systemd unit: `sudo cp sonic/mainnet-sonic-rpc.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable mainnet-sonic-rpc`.

---

## Start order (single host)

1. **BTC**: `docker compose -f /home/mainnet/btc/docker-compose.yml up -d`
2. **BCH**: `docker compose -f /home/mainnet/bch/docker-compose.yml up -d`
3. **XLM**: `docker compose -f /home/mainnet/xlm/docker-compose.yml up -d` (postgres → stellar-core → horizon, stellar-rpc)
4. **TRX**: `docker compose -f /home/mainnet/trx/docker-compose.yml up -d`
5. **AVAX**: `docker compose -f /home/mainnet/avax/docker-compose.yml up -d`
6. **SONIC**: `sudo systemctl start mainnet-sonic-rpc` (after one-time install and tuning)

---

## Directory layout

```
/home/mainnet/
├── tools/
│   ├── README.md          (this file)
│   └── bin/               (optional health/helper scripts)
├── btc/                   Bitcoin Core (Docker)
├── bch/                   Bitcoin Cash Node (Docker)
├── xlm/                   Stellar core + Horizon + Stellar RPC (Docker)
├── trx/                   Tron (Docker)
├── avax/                  Avalanche (Docker)
└── sonic/                 Sonic RPC (systemd)
```

---

## Security

- For **BTC** and **BCH**, set strong `rpcpassword` and use `rpcallowip` to restrict RPC access; put a firewall or reverse proxy in front if exposing publicly.
- Do not expose RPC ports to the internet without authentication/TLS unless intended.
