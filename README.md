# claude-code-local-mlx

Run [Claude Code](https://docs.anthropic.com/en/docs/claude-code) against a local MLX model on Apple Silicon. One command, no config files.

This tool starts a local proxy server ([claude-code-mlx-proxy](https://github.com/chand1012/claude-code-mlx-proxy)) that translates Claude Code's API calls into local MLX model inference, then launches Claude Code pointed at it.

## Prerequisites

- **Apple Silicon Mac** (M1/M2/M3/M4) — MLX only runs on Apple chips
- **[uv](https://docs.astral.sh/uv/)** — Python package manager
- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** — Anthropic's CLI (`npm install -g @anthropic-ai/claude-code`)
- **git** — to clone the proxy repo on first run

## Quick start

```bash
# Run with the default model (Qwen3-Coder-Next-8bit):
uv tool run --from git+https://github.com/GuillaumeBlanchet/claude-code-local-mlx.git claude-local
```

That's it. On first run it will:

1. Clone the proxy server
2. Download the model from HuggingFace (if not cached)
3. Start the proxy on port 18808
4. Launch Claude Code connected to your local model

On subsequent runs, if the proxy is already running, it skips straight to launching Claude Code.

## Install permanently

```bash
uv tool install git+https://github.com/GuillaumeBlanchet/claude-code-local-mlx.git
```

Then just run `claude-local` from anywhere.

## Usage

```
claude-local                                        # start proxy + Claude Code
claude-local --model mlx-community/Other-Model-4bit # use a different model
claude-local --server                               # start proxy only
claude-local --kill                                 # stop the proxy
claude-local --restart                              # force restart the proxy
claude-local --port 9999                            # use a custom port
```

All other flags pass through to Claude Code:

```bash
claude-local -p "Explain this codebase"             # non-interactive (print mode)
claude-local -c                                     # continue last conversation
```

## Choosing a model

The default model is `mlx-community/Qwen3-Coder-Next-8bit`, an 80B MoE model optimized for coding. You can use any MLX model from HuggingFace:

```bash
# Smaller, faster
claude-local -m mlx-community/Qwen3-30B-A3B-4bit

# Larger, higher quality
claude-local -m mlx-community/Qwen3.5-Coder-72B-4bit
```

### Memory requirements

| Model | Quantization | RAM needed |
|---|---|---|
| Qwen3-Coder-Next | 4-bit | ~25 GB |
| Qwen3-Coder-Next | 8-bit | ~45 GB |
| Qwen3.5-Coder-72B | 4-bit | ~40 GB |

Models are downloaded from HuggingFace on first use and cached in `~/.cache/huggingface/`.

## How it works

```
┌─────────────┐     Anthropic       ┌──────────────────┐      MLX       ┌──────────────┐
│ Claude Code  │ ──  Messages API ──▶│  mlx-proxy       │ ──  inference ─▶│  Local Model  │
│   (CLI)      │ ◀── /v1/messages ──│  (localhost:18808)│ ◀── tokens ────│  (Apple GPU)  │
└─────────────┘                     └──────────────────┘               └──────────────┘
```

- **Claude Code** is Anthropic's official coding CLI. It supports custom API endpoints via `ANTHROPIC_BASE_URL`.
- **claude-code-mlx-proxy** is a lightweight FastAPI server that translates the Anthropic Messages API into MLX model calls.
- **MLX** is Apple's machine learning framework optimized for Apple Silicon's unified memory.

## Data locations

| What | Where |
|---|---|
| Proxy server repo | `~/.local/share/claude-local/proxy/` |
| Proxy log | `~/.local/state/claude-mlx-proxy.log` |
| Proxy PID file | `~/.local/state/claude-mlx-proxy.pid` |
| Model cache | `~/.cache/huggingface/hub/` |

## Troubleshooting

**Proxy fails to start:**
```bash
cat ~/.local/state/claude-mlx-proxy.log
```

**Force a clean restart:**
```bash
claude-local --kill
rm -rf ~/.local/share/claude-local
claude-local
```

**Model too large for your RAM:**
Try a smaller quantization or a smaller model with `--model`.

## License

MIT
