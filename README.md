# claude-code-local-mlx

Run [Claude Code](https://docs.anthropic.com/en/docs/claude-code) against a local MLX model on Apple Silicon. One command, no config files.

> Read the full blog post: [Run Claude Code With a Local Model on Your Mac](https://ducttapecode.com/blog/claude-code-local-mlx/article/)

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

Pick the best model for your machine. **Runtime RAM is significantly larger than model file size** due to the KV cache, tokenizer, and framework overhead. The numbers below are **real-world measurements**, not just file sizes. Rule of thumb: budget 50-80% more RAM than the on-disk weight size.

| RAM | Recommended Model | Quant | Runtime RAM | tok/s (M4 Max) | Comparable to | Benchmark basis |
|-----|-------------------|-------|-------------|----------------|---------------|-----------------|
| **8 GB** | `mlx-community/Qwen2.5-Coder-3B-Instruct-4bit` | 4-bit | ~3-4 GB | ~200 | GPT-3.5 Turbo (older) | Aider Edit: ~39% vs GPT-3.5's ~50% |
| **16 GB** | `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | 4-bit | ~7-8 GB | ~90 | GPT-4o-mini | Aider Edit: ~58% vs 4o-mini's 56% |
| **24 GB** | `mlx-community/Gemma-4-26b-a4b-it-4bit` | 4-bit | ~17-20 GB | ~110 (MoE) | GPT-4o (code gen) | HumanEval: 88%; LiveCodeBench: 77% |
| **32 GB** | `mlx-community/Qwen2.5-Coder-32B-Instruct-4bit` | 4-bit | ~25-30 GB | ~14-30 | GPT-4o (editing) | Aider Edit: 71% vs GPT-4o's 73% |
| **48 GB** | `mlx-community/Qwen3-Coder-Next-4bit` | 4-bit | ~40-46 GB | ~40-60 (MoE) | Claude Sonnet 4 (no thinking) | Aider Polyglot: 50% vs Sonnet 4's 56%; SWE-bench: 71-74% |
| **64 GB** | `mlx-community/Qwen2.5-Coder-32B-Instruct-8bit` | 8-bit | ~33 GB | ~10-14 | GPT-4o (near-lossless) | Same as 4-bit, ~0% quality loss on MLX |
| **96 GB** | `mlx-community/Qwen3-Coder-Next-8bit` | 8-bit | **~79 GB** | ~35-50 (MoE) | Claude Sonnet 4 (no thinking) | SWE-bench: 71-74%; best quality local coder |
| **128 GB** | `mlx-community/Devstral-2-123B-Instruct-2512-4bit` | 4-bit | ~72-90 GB | ~5-8 | GPT-4.1 / Claude 3.5 Sonnet | SWE-bench Verified: ~70%. Slow but capable. |

> **About tok/s:** MoE models (Gemma 4, Qwen3-Coder-Next) are much faster than dense models of similar total size because only a fraction of parameters are active per token. The tok/s column shows M4 Max figures -- scale roughly proportionally with your chip's memory bandwidth (M4 Pro ~0.5x, M3 Ultra ~1.5x, M2 Ultra ~1.5x).

### How to read the "Comparable to" column

These comparisons are based on **raw benchmark scores** (Aider Polyglot, SWE-bench Verified, HumanEval). They indicate the commercial model your local model performs closest to **on standardized coding benchmarks**. The actual experience may be better -- see the section on [harness boost](#the-harness-boost-why-your-local-model-will-punch-above-its-weight) below.

### Runner-up picks

| RAM | Alternative | Notes |
|-----|------------|-------|
| 24 GB | `mlx-community/Qwen3-Coder-Next-4bit` | 80B MoE, ~40 GB runtime -- tight fit, but great for agentic coding if it fits. |
| 32 GB | `mlx-community/Devstral-Small-2-24B-Instruct-2512-4bit` | 24B, ~20 GB runtime. 68% SWE-Bench. Leaves room for other apps. |
| 48 GB | `mlx-community/Qwen2.5-Coder-32B-Instruct-8bit` | 32B dense (~33 GB). Near-lossless 8-bit, room for long context. |
| 64 GB | `mlx-community/Gemma-4-31b-it-4bit` | 31B dense (~23 GB). 80% LiveCodeBench v6. Great general + code. |
| 128 GB | `mlx-community/Qwen3-Coder-Next-8bit` | 80B MoE (~79 GB). Faster than Devstral 123B, excellent quality. |

### Example

```bash
# On a 32 GB MacBook Pro:
claude-local -m mlx-community/Qwen2.5-Coder-32B-Instruct-4bit

# On a 24 GB MacBook:
claude-local -m mlx-community/Gemma-4-26b-a4b-it-4bit
```

Models are downloaded from HuggingFace on first use and cached in `~/.cache/huggingface/`.

## The harness boost: why your local model will punch above its weight

Most coding benchmarks (Aider, SWE-bench, HumanEval) test models with **basic scaffolding** -- a simple loop of "read prompt, generate code, check." But Claude Code is a **modern agentic harness**: it has tool use, file editing, shell access, retry logic, multi-step planning, and context management.

Research shows that the harness matters **more than the model** at the frontier:

| Study | Same model, basic scaffold | Same model, optimized scaffold | Improvement |
|-------|---------------------------|-------------------------------|-------------|
| Claude Opus 4.5 on CORE-Bench | 42% | 78% (with Claude Code) | **+36 points** |
| LangChain coding agent | 52.8% | 66.5% | **+14 points** |
| SWE-bench Pro analysis | ~1 pt difference from model swaps | ~22 pt difference from scaffold swaps | **Scaffold >> Model** |

*Source: [Agent Scaffolding Beats Model Upgrades (Particula)](https://particula.tech/blog/agent-scaffolding-beats-model-upgrades-swe-bench)*

**What this means for you:** The benchmark scores above were measured with **basic harnesses from 2024-2025**. Claude Code's agentic capabilities (tool use, iterative editing, error recovery) can boost effective performance by **15-35 points** compared to those benchmarks.

In practice:
- A **Qwen2.5-Coder-32B** that benchmarks like GPT-4o in isolation can perform closer to **Claude 3.5 Sonnet** when harnessed by Claude Code
- A **Qwen3-Coder-Next** that benchmarks like Claude Sonnet 4 (no thinking) can approach **Claude Sonnet 4 (with thinking)** territory with proper agentic scaffolding
- A **Devstral-2-123B** that benchmarks near Claude Sonnet 4 can punch into **frontier-class** effectiveness

The model provides the intelligence; the harness multiplies it. You're getting both.

## Why MLX over Ollama?

Both are valid ways to run local models with Claude Code. Here's how they compare.

### Ollama now works with Claude Code directly

As of 2026, [Ollama has native Claude Code integration](https://docs.ollama.com/integrations/claude-code). Setup is simple:

```bash
ollama launch claude                              # interactive picker
ollama launch claude --model qwen3.5              # specific model
```

Or manually:

```bash
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL=http://localhost:11434
claude --model qwen3.5
```

Ollama now exposes an **Anthropic-compatible API**, so no translation proxy is needed. If you want the easiest setup, **Ollama is the simpler path**.

### So why use this tool instead?

This tool uses `mlx-lm` directly with native MLX models. The tradeoffs:

| | **Ollama** | **This tool (mlx-lm)** |
|---|---|---|
| **Setup** | One command (`ollama launch claude`) | One command (`claude-local`) |
| **Model format** | GGUF (llama.cpp format) | Native MLX safetensors |
| **Quantization** | Q4_K_M, Q5_K_M, etc. | 2/3/4/5/6/8-bit, MXFP4, DWQ |
| **Inference speed** | ~112 tok/s (MLX backend) | ~130 tok/s |
| **Memory overhead** | Higher (GGUF-to-MLX conversion, HTTP layer) | Lower (zero-copy, in-process) |
| **Model selection** | Ollama registry only | Any `mlx-community/` HuggingFace model |

### Performance difference

Head-to-head benchmarks on the same hardware:

| Engine | Decode speed | Relative |
|--------|-------------|----------|
| **MLX (mlx-lm)** | ~130 tok/s | **1.0x** |
| Ollama v0.19 (MLX backend) | ~112 tok/s | 0.86x |
| llama.cpp | ~71 tok/s | 0.55x |
| Ollama (pre-MLX) | ~45 tok/s | 0.35x |

*Benchmark: Qwen3.5-35B on M4 Max. Source: [antekapetanovic.com](https://antekapetanovic.com/blog/qwen3.5-apple-silicon-benchmark/)*

The ~15-20% speed advantage comes from:
- **No HTTP/JSON layer** -- mlx-lm runs in-process, Ollama serializes every request/response over HTTP
- **Native MLX models** -- loaded directly into unified memory, no GGUF-to-MLX conversion at runtime
- **MLX-optimized quantization** -- formats like MXFP4 and DWQ are designed for Apple Silicon's Metal GPU and aren't available in GGUF

For a coding agent making hundreds of API calls per session, the overhead compounds. On a 30-minute coding session, you might save 3-5 minutes of wall-clock time.

### Memory efficiency

MLX was designed for Apple Silicon's **unified memory architecture** (UMA):

- **MLX**: Tensors live in unified memory. The GPU reads model weights in-place -- zero copy.
- **Ollama**: Even with the MLX backend, Ollama uses GGUF format which requires conversion, plus the HTTP server adds buffer overhead.
- **Result**: A model that uses 20 GB in MLX can need 22-25 GB in Ollama. This matters when you're fitting a model at the edge of your RAM.

### Quantization quality

Independent benchmarks show MLX 4-bit quantization preserves ~95-98% of full-precision quality for coding tasks. [One study on Qwen2.5-Coder](https://medium.com/@ivanfioravanti/qwen-2-5-coder-quantization-does-not-matter-aider-benchmarks-on-apple-mlx-671e6bd5252a) found "quantization does not matter" on Aider benchmarks when using MLX.

MLX-native quantization (MXFP4, DWQ) tends to preserve more quality at the same bit width than GGUF equivalents because the quantization is co-designed with Apple's Metal compute kernels.

### The bottom line

**Choose Ollama** if you want the simplest setup and don't mind ~15% slower inference.

**Choose this tool** if you want maximum performance, lower memory usage, access to the full `mlx-community/` model catalog on HuggingFace, and MLX-native quantization formats.

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

- [Aider LLM Leaderboards](https://aider.chat/docs/leaderboards/) -- Polyglot (hard) and Edit (easy) benchmarks
- [Aider Polyglot on llm-stats](https://llm-stats.com/benchmarks/aider-polyglot) -- aggregated scores
- [SWE-bench Verified Leaderboard](https://www.swebench.com/) -- real-world GitHub issue resolution
- [Gemma 4 vs Qwen3.5 Local Coding Benchmark](https://msf.github.io/blogpost/local-llm-coding-harder-test.html)
- [Qwen3.5 Apple Silicon Benchmark (MLX vs Ollama vs llama.cpp)](https://antekapetanovic.com/blog/qwen3.5-apple-silicon-benchmark/)
- [Agent Scaffolding Beats Model Upgrades (Particula)](https://particula.tech/blog/agent-scaffolding-beats-model-upgrades-swe-bench)
- [Ollama MLX Backend Announcement](https://ollama.com/blog/mlx)
- [Qwen2.5-Coder Quantization Study on MLX](https://medium.com/@ivanfioravanti/qwen-2-5-coder-quantization-does-not-matter-aider-benchmarks-on-apple-mlx-671e6bd5252a)
- [Apple Silicon LLM Optimization Guide](https://blog.starmorph.com/blog/apple-silicon-llm-inference-optimization-guide)

## License

[MIT](LICENSE)
