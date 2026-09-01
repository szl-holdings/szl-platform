#!/bin/bash
# vast_sovereign_node.sh — bootstrap a vast.ai GPU box into a governed sovereign node.
# What it builds: Ollama (llama3.1:8b) -> LiteLLM proxy (model id "sovereign-llm",
# bearer-locked via $LITELLM_MASTER_KEY) -> szl-evidence-litellm receipt plugin
# (every request emits a hash-chained DSSE receipt) -> Caddy TLS for
# gpu-cloud.a-11-oy.com -> reverse proxy to LiteLLM. All logs in /root/*.log.
set -ex
export DEBIAN_FRONTEND=noninteractive

apt-get update -y
apt-get install -y curl git python3 python3-pip ca-certificates

# --- Ollama ---
curl -fsSL https://ollama.com/install.sh | sh
nohup ollama serve > /root/ollama.log 2>&1 &
for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/version && break; sleep 2; done
ollama pull llama3.1:8b

# --- LiteLLM + the SZL evidence plugin (public repo, pinned by commit on push) ---
pip3 install --no-cache-dir "litellm[proxy]"
pip3 install --no-cache-dir \
  "git+https://github.com/szl-holdings/szl-platform.git#subdirectory=packages/szl-receipts" \
  "git+https://github.com/szl-holdings/szl-platform.git#subdirectory=packages/szl-evidence-litellm"

mkdir -p /root/evidence
cat > /root/litellm_config.yaml <<'CFG'
model_list:
  - model_name: sovereign-llm
    litellm_params:
      model: ollama/llama3.1:8b
      api_base: http://127.0.0.1:11434
litellm_settings:
  callbacks: ["szl_evidence_litellm.plugin.SZLEvidenceLogger"]
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
CFG

# --- Caddy (static binary; ACME HTTP-01 on :80, TLS on :443) ---
curl -fsSL -o /tmp/caddy.tar.gz "https://caddyserver.com/api/download?os=linux&arch=amd64"
tar -xzf /tmp/caddy.tar.gz -C /usr/bin caddy
chmod +x /usr/bin/caddy
cat > /etc/caddy/Caddyfile <<'CFG'
gpu-cloud.a-11-oy.com {
    reverse_proxy 127.0.0.1:4000
}
CFG

nohup litellm --config /root/litellm_config.yaml --port 4000 > /root/litellm.log 2>&1 &
nohup caddy run --config /etc/caddy/Caddyfile > /root/caddy.log 2>&1 &
echo BOOTSTRAP-DONE
