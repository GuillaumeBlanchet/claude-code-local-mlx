# claude-code-local-mlx

Run [Claude Code](https://docs.anthropic.com/en/docs/claude-code) against a local MLX model on Apple Silicon. One command, no config files.

This tool starts a local proxy server ([claude-code-mlx-proxy](https://github.com/chand1012/claude-code-mlx-proxy)) that translates Claude Code's API calls into local MLX model inference, then launches Claude Code pointed at it.

## Prerequisites

- **Apple Silicon Mac** (M1/M2/M3/M4) -- MLX only runs on Apple chips
- **[uv](https://docs.astral.sh/uv/)** -- Python package manager
- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** -- Anthropic's coding CLI
- **git**

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

On subsequent runs, if the proxy is already running, it reuses it instantly.

## Install permanently

```bash
uv tool install git+https://github.com/GuillaumeBlanchet/claude-code-local-mlx.git
```

Then just run `claude-local` from anywhere.

## Usage

```
claude-local                                        # start proxy + Claude Code
claude-local -m mlx-community/Other-Model-4bit      # use a different model
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

## Recommended models by RAM

Pick the best model for your machine. Rule of thumb: the model should use **~70% of your RAM** to leave room for macOS and the KV cache.

| RAM | Recommended Model | Params | Quant | ~RAM Usage | Why |
|-----|-------------------|--------|-------|------------|-----|
| **8 GB** | `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` | 3B dense | 4-bit | ~2.5 GB | Best coding-specific model at this size. Fast (~35 tok/s). |
| **16 GB** | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | 7B dense | 4-bit | ~4.5 GB | Dedicated coding model; outperforms general-purpose 8B models on code. |
| **24 GB** | `mlx-community/Gemma-4-26b-a4b-it-4bit` | 26B MoE (4B active) | 4-bit | ~15 GB | Top local coding model per independent benchmarks. Rock-solid compilation rate. |
| **32 GB** | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` | 32B dense | 4-bit | ~18.5 GB | Gold standard for local coding. Purpose-built, quantization barely hurts quality. |
| **48 GB** | `mlx-community/Qwen2.5-Coder-32B-Instruct-8bit` | 32B dense | 8-bit | ~34 GB | Same gold standard at near-lossless 8-bit. Room for large context windows. |
| **64 GB** | `mlx-community/Qwen3-Coder-Next-8bit` | 80B MoE (3B active) | 8-bit | ~45 GB | 80B-knowledge coding specialist at high fidelity. 256K context. Default model. |
| **96 GB** | `mlx-community/Devstral-2-123B-Instruct-2512-4bit` | 123B dense | 4-bit | ~65 GB | Mistral's full-size coding agent. 72.2% SWE-Bench Verified. |
| **128 GB** | `mlx-community/Devstral-2-123B-Instruct-2512-8bit` | 123B dense | 8-bit | ~90 GB | Same model at near-lossless 8-bit. Maximum coding quality you can run locally. |

### Runner-up picks

| RAM | Alternative | Notes |
|-----|------------|-------|
| 24 GB | `mlx-community/Qwen3-Coder-Next-4bit` | 80B MoE, 3B active (~20 GB). Great for agentic coding. |
| 32 GB | `mlx-community/Devstral-Small-2-24B-Instruct-2512-4bit` | 24B, ~14 GB. 68% SWE-Bench. Leaves room for other apps. |
| 48 GB | `mlx-community/Qwen3-Coder-Next-8bit` | 80B MoE (~45 GB). Best if you prefer coding-specialist MoE over dense. |
| 64 GB | `mlx-community/Gemma-4-31b-it-8bit` | 31B dense. 80% LiveCodeBench v6. Great general + code. |

### Example

```bash
# On a 32 GB MacBook Pro:
claude-local -m mlx-community/Qwen2.5-Coder-32B-Instruct-4bit

# On a 24 GB MacBook:
claude-local -m mlx-community/Gemma-4-26b-a4b-it-4bit
```

Models are downloaded from HuggingFace on first use and cached in `~/.cache/huggingface/`.

## Why MLX over Ollama?

Both are great tools, but MLX has structural advantages on Apple Silicon:

### Performance: ~2x faster inference

MLX is purpose-built for Apple's Metal GPU. Head-to-head benchmarks on the same hardware show:

| Engine | Decode speed | Relative |
|--------|-------------|----------|
| **MLX (mlx-lm)** | ~130 tok/s | **1.0x** |
| llama.cpp | ~71 tok/s | 0.55x |
| Ollama (pre-MLX) | ~45 tok/s | 0.35x |

*Benchmark: Qwen3.5-35B on M4 Max. Source: [antekapetanovic.com](https://antekapetanovic.com/blog/qwen3.5-apple-silicon-benchmark/)*

> **Note:** Ollama v0.19+ (March 2026) added an MLX backend, which closes the gap to ~112 tok/s. But using mlx-lm directly still avoids the HTTP/JSON serialization overhead (~15-20%).

### Memory: zero-copy unified memory

MLX was designed for Apple Silicon's **unified memory architecture** (UMA):

- **MLX**: Tensors live in unified memory. The GPU reads model weights in-place -- zero copy.
- **Ollama/llama.cpp**: Originally designed for discrete GPUs, they copy data between CPU and GPU address spaces, wasting bandwidth and duplicating memory.
- **Result**: A model that uses 20 GB in MLX can need 22-25 GB in Ollama due to buffer overhead. This matters when you're fitting a model at the edge of your RAM.

### Quantization: more options, better quality

MLX supports native quantization formats optimized for Apple hardware:

- **MLX**: 2/3/4/5/6/8-bit group quantization, MXFP4, DWQ (Data-Aware Weighted Quantization)
- **Ollama**: GGUF format only (Q4_K_M, Q5_K_M, etc.)

Independent benchmarks show MLX 4-bit quantization preserves ~95-98% of full-precision quality for coding tasks. [One study on Qwen2.5-Coder](https://medium.com/@ivanfioravanti/qwen-2-5-coder-quantization-does-not-matter-aider-benchmarks-on-apple-mlx-671e6bd5252a) found "quantization does not matter" on Aider benchmarks when using MLX.

### The bottom line

Ollama is simpler to set up and has a larger ecosystem. MLX gives you faster inference, better memory efficiency, and higher-quality quantization. For coding agents (where speed directly impacts productivity), MLX is the better choice on Apple Silicon.

> Fun fact: As of Ollama v0.19, Ollama itself uses MLX under the hood on Apple Silicon -- validating MLX as the standard for local inference on Macs.

## How it works

```
┌─────────────┐     Anthropic       ┌──────────────────┐      MLX       ┌──────────────┐
│ Claude Code  │ ── Messages API ──>│  mlx-proxy       │ ── inference ──>│  Local Model  │
│   (CLI)      │ <── /v1/messages ──│  (localhost:18808)│ <── tokens ────│  (Apple GPU)  │
└─────────────┘                     └──────────────────┘                └──────────────┘
```

- **Claude Code** is Anthropic's official coding CLI. It supports custom API endpoints via `ANTHROPIC_BASE_URL`.
- **[claude-code-mlx-proxy](https://github.com/chand1012/claude-code-mlx-proxy)** is a lightweight FastAPI server that translates the Anthropic Messages API into MLX model calls.
- **[MLX](https://github.com/ml-explore/mlx)** is Apple's machine learning framework optimized for Apple Silicon's unified memory.

## Data locations

| What | Where |
|------|-------|
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
Use the [model table](#recommended-models-by-ram) to pick one that fits your machine.

## Benchmark sources

- [Aider LLM Leaderboards](https://aider.chat/docs/leaderboards/)
- [Gemma 4 vs Qwen3.5 Local Coding Benchmark](https://msf.github.io/blogpost/local-llm-coding-harder-test.html)
- [Qwen3.5 Apple Silicon Benchmark (MLX vs Ollama vs llama.cpp)](https://antekapetanovic.com/blog/qwen3.5-apple-silicon-benchmark/)
- [Ollama MLX Backend Announcement](https://ollama.com/blog/mlx)
- [Qwen2.5-Coder Quantization Study on MLX](https://medium.com/@ivanfioravanti/qwen-2-5-coder-quantization-does-not-matter-aider-benchmarks-on-apple-mlx-671e6bd5252a)
- [Apple Silicon LLM Optimization Guide](https://blog.starmorph.com/blog/apple-silicon-llm-inference-optimization-guide)

## License

[MIT](LICENSE)
