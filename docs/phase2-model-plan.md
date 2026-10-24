> **File use case:** Phase-2 model plan for replacing hosted DeepSeek with a self-hosted model under USD 200/month.
> **What it does:** Records the October 22 study, recommendation (Qwen3.6-35B-A3B), hardware/pricing, architecture options and go/no-go evaluation plan. Figures are estimates until benchmarked.

# Replacing DeepSeek V4 Pro with a self-hosted model in Syntelio (SLM study, phase-2 architecture)

Date: 2026-10-22. This is research only, with no code or config changes. Every price and benchmark below comes from a public page on the date shown. Items marked **[unverified]** are estimates or have only one weak source.

## 0. Short answer

- **Recommendation:** run one model for every job: **Qwen3.6-35B-A3B** (Apache-2.0, a mixture-of-experts model with 35B total and 3B active parameters) at **Q4_K_M GGUF**.
  - Serve it with **llama.cpp `llama-server`** on **one rented 24 GB GPU** (RTX 3090 or 4090 from a monthly marketplace, about **$100–200/month**).
  - Thinking mode stays off, and every call is JSON-constrained.
  - It plugs into the existing OpenAI-compatible adapter through environment variables only.
- **Fallback with no new spend:** **Qwen3.5-9B Q4_K_M** on the current VPS's Tesla P100.
  - The P100 already has about 7.8 GB taken by other apps, which leaves roughly 8.5 GB.
  - Expect noticeably weaker explanations and slower calls.
- **Honest expectation:** the open model can come close to DeepSeek V4 Pro on *constrained* work: route choice, column selection and JSON plans over a known schema, all checked by our server validators.
  - It is expected to be weaker on long, nuanced explanations and on Roman Urdu. No public Urdu or Roman Urdu benchmark covers these models; this is **[unverified]**.
  - DeepSeek V4 Pro is a 1.6T-parameter MoE with 49B active parameters. No model under 35B is "the same" in general. The plan in section 7 measures whether the gap matters *for our tasks*.
- **Option C (a judge model) is not recommended at launch.** Deterministic validators already do most of a judge's job. A judge should only be trialled later on low-confidence cases (section 2).

## 1. What we actually ask the model to do (grounding)

Sources: `docs/agent-deepseek-architecture-for-review.md`, `docs/agent-harness.md`, `docs/insights-engine.md`, `apps/api/src/execplus/config.py`, `infrastructure/models/openai_compatible.py`.

- The model never computes numbers. DuckDB and SciPy tools do the maths, and the server validates the typed proposals.
- Calls today:
  - **Optional local advisory selector:** Qwen3-4B on Ollama 0.20.0 at `127.0.0.1:11450`. It runs in JSON mode with 512 output tokens and `reasoning_effort=none`.
  - **Main planner on DeepSeek:** sees the capability catalogue, the full visible schema (not token-packed), definitions, profile, goal and context. It returns JSON in message content with a 1024-token default output and a 40 s shared budget.
  - **Qualitative reading or explanation:** at most 2 calls sharing 40 s.
  - **Upload brief:** default output of 4,096 tokens.
- **No provider `tools` / `tool_calls` are used.** Everything is "JSON object in content", so native function-calling quality matters less than JSON discipline and schema grounding.
- **Typical pattern:** a prompt of about 2–4k tokens, a JSON output of 1k tokens or less, and 1–3 calls per question.

## 2. Phase-2 architecture options

### Option A: one SLM for everything (recommended)

- Covers routing, column selection, planning JSON, readings, briefs and multilingual text.
- **Pros:**
  - One model in VRAM.
  - One endpoint, set as both `EXECPLUS_LLM_BASE_URL` and `EXECPLUS_LLM_SELECTION_BASE_URL` with the same model name.
  - Simplest operations.
  - Removes the serial selector call, which the architecture review already questions (section 12: "Measure whether the selector improves decisions enough to justify latency").
- **Cons:** the model has to be good at both short JSON and longer prose. Qwen3.6-35B-A3B covers both acceptably according to its vendor benchmarks.

### Option B: small router plus larger planner

- Example: keep Qwen3-4B, or move to Qwen3.5-4B or 9B, as the selector next to the 35B-A3B planner.
- On a 24 GB card a second model costs about 3–6 GB of VRAM, which squeezes KV cache and context for the 35B model.
- It also adds a serial call to every question.
- **Use only if** the evaluation shows the selector hint improves planner accuracy. With a MoE planner at roughly 100 tok/s, a separate router saves almost no latency.

### Option C: generator plus judge/verifier

- **What failed before:** `docs/verification-phase3d.md` records a *free-form* DeepSeek judge.
  - It scored 5/12 exact matches, had 6 timeouts and misclassified one defect.
  - Its p95 latency was about 10 s.
- **What would be different now:**
  1. **Deterministic validators run first, and they already exist.** These are the typed proposal validation (`domain/intent.py::route_response`), semantic and requirement checks, units guards, receipt checks and the claim filters on narratives. A judge must never replace them.
  2. **Grammar-constrained decoding.** `llama-server` turns `response_format` (`json_object`, or `json_schema` when we pass one) into a GBNF grammar. The output then cannot be malformed JSON, which removes a whole class of retry and correction calls.
  3. **The judge runs only on low-confidence cases.** Examples: a validator corrected the plan, the plan uses a column not mentioned in the question, the plan contradicts a recognised category label, or the narrative cites a number not in the receipt.
     - It would get a **closed-form question**: "Does plan X answer question Q given schema S? Reply `{"verdict": "ok" | "mismatch", "field": ...}`".
     - That is a classification task, not open grading.
  4. **The same model in judge mode** costs no extra VRAM, and there are no network timeouts on a local box.
- **Recommendation:** do not build Option C now. Re-run the frozen 12-case Phase 3D set against the local model in this closed-form mode. Adopt it only if it beats the old 5/12 by a wide margin, at least 10/12 with zero timeouts. Otherwise rely on deterministic validators plus one correction retry, which is the current behaviour.

## 3. Candidate models (current as of October 2026)

| Model | Params (active) | License | Vendor benchmarks (selected) | Q4 size (approx.) | Notes |
|---|---|---|---|---|---|
| **Qwen3.6-35B-A3B** | 35B MoE (3B) | Apache-2.0 | MMLU-Pro 85.2; TAU3 67.2 ([card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B), Apr 2026) | ~21 GB | Fast because only 3B parameters are active. Thinking is on by default and must be turned off. Gated-DeltaNet hybrid architecture. |
| Qwen3.6-27B | 27B dense | Apache-2.0 | MMLU-Pro 86.2 ([card](https://huggingface.co/Qwen/Qwen3.6-27B), collection Apr 2026; one tracker lists Oct 21 **[conflicting date]**) | ~16.5 GB | Slightly stronger but about 3–4× slower to decode than the A3B model. |
| Qwen3.5-27B | 27B dense | Apache-2.0 | BFCL-V4 68.5, TAU2 ~79 ([card](https://huggingface.co/Qwen/Qwen3.5-27B), Feb 2026; BFCL value read from table via search **[partly unverified]**) | ~16.5 GB | |
| **Qwen3.5-9B** | 9B dense | Apache-2.0 | BFCL-V4 66.1, TAU2 79.1, IFEval 91.5, MMLU-Pro 82.5, MMMLU 81.2, INCLUDE 75.6 ([card](https://huggingface.co/Qwen/Qwen3.5-9B), Feb–Mar 2026) | ~5.7–6.6 GB | Best small model per GB. Claims 201 languages; Urdu is not individually confirmed. |
| Gemma 4 31B / 26B-A4B | 31B dense / 26B MoE (3.8B) | Apache-2.0 | MMLU-Pro 85.2 / 82.6; Tau2 76.9 / 68.2; MMMLU 88.4 / 86.3 ([card](https://huggingface.co/google/gemma-4-31B-it), Apr–Jul 2026) | ~18 / ~16 GB | Strongest multilingual MMMLU in this range. Pre-trained on 140+ languages. Native function calling. A strong second candidate. |
| Gemma 4 E4B | ~4.5B effective | Apache-2.0 | MMLU-Pro 69.4, Tau2 42.2 | ~3–5 GB | Too weak for the planner role. |
| Ministral 3 8B / 14B | 8B / 14B | Apache-2.0 | Vendor claims native function calling and JSON output; no BFCL figure found ([LM Studio](https://lmstudio.ai/models/ministral)) | 5 / 9 GB | **[unverified]** for our tasks. |
| IBM Granite 4.x, Phi-4-mini, SmolLM | — | open | No current BFCL or multilingual numbers found in this search | — | Not shortlisted. |

- **Function-calling leaderboards:** the best open BFCL-V4 entries are large models (Qwen3.5-397B at about 72.9; [aggregator, Sep 2026](https://benchlm.ai/benchmarks/bfcl-v4)). Qwen3.5-9B and 27B at 66–68 are close to those. The official BFCL board was not checked directly **[unverified]**.
- **Text-to-SQL:** this matters less because we emit typed plans, not SQL. On BIRD dev, open 7B–32B models reach about 39–52% EX ([arXiv 2606.29733](https://arxiv.org/abs/2606.29733), Jun 2026), against more than 80% for top systems. This is a reminder that our server-side validation and clarification are what make small models safe here.
- **Urdu and Roman Urdu:** I found no 2026 benchmark covering Qwen3.5/3.6 or Gemma 4. UrduBench ([arXiv 2601.21000](https://arxiv.org/html/2601.21000v1)) found Gemma 3 the strongest open model in Urdu reasoning. This hints that Gemma 4 may be better than Qwen at Urdu **[unverified]**. Our own Roman Urdu cases must decide this.
- **DeepSeek V4 Pro:**
  - Open weights, 1.6T parameters / 49B active ([HF](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro), Apr 2026).
  - MMLU-Pro 87.5 with maximum reasoning and **82.9 in non-thinking mode**, which is how we call it.
  - It is impossible to self-host under $200.
  - On paper, Qwen3.6-35B-A3B's 85.2 is in the same range, but the vendors' settings differ, so this is not apples-to-apples.

## 4. Hardware

### 4.1 Current VPS (measured read-only, 2026-10-22)

- CPU: 2 × Intel Xeon E5-2690 (Sandy Bridge, 2012), 32 threads.
  - It has **AVX only, with no AVX2, FMA or AVX-512** (taken from the `lscpu` flags).
  - llama.cpp's fast CPU kernels need AVX2, so CPU inference is slow here.
- RAM: 125 GiB, with 117 GiB available. Disk: 857 GB free on `/sdb-disk`.
- GPU: **Tesla P100 16 GB (Pascal, sm_60)**, driver 550 / CUDA 12.4.
  - **7.8 GB is already used by two other apps' Python processes**, so only about 8.5 GB is free.
  - No Syntelio/Ollama process was on the GPU at the time. The model may be idle-unloaded, or running on the CPU. **[unverified]:** I was limited to the listed commands, so `ollama ps` was not run.
- **What this means:**
  - vLLM has no practical Pascal path ([PyTorch 2.15 drops sm_60 wheels](https://dev-discuss.pytorch.org/t/notice-cuda-12-6-wheels-will-no-longer-be-published-from-pytorch-2-15-drops-maxwell-pascal-volta/3432); vLLM ≥0.20 reportedly dropped sm_70 too). llama.cpp or Ollama with CUDA is the only option.
  - In the free ~8.5 GB, the realistic ceiling is a 9B model at Q4.
  - The 35B-A3B model with experts offloaded to this AVX-only CPU is expected to be slow (roughly 3–8 tok/s **[unverified estimate]**).
  - If the other apps' GPU use could be moved, the full 16 GB would allow Gemma 4 26B-A4B or Qwen3.6-35B-A3B at about 3-bit. That is still slow on Pascal, and only partly fits.
- Known P100 speeds (Ollama, Q4; [DatabaseMart](https://www.databasemart.com/blog/ollama-gpu-benchmark-p100), updated 2026-10-21, old models):
  - Qwen2.5-7B: 34.7 tok/s.
  - Llama3.1-8B: 33.0 tok/s.
  - Qwen2.5-14B: 19.5 tok/s.
  - Gemma2-9B: 29.5 tok/s.

### 4.2 Rentable options under $200/month (prices as published; check before ordering)

| Option | GPU / VRAM | Price | Fits Qwen3.6-35B-A3B Q4? | Notes |
|---|---|---|---|---|
| **Vast.ai RTX 3090** (marketplace) | 24 GB | ~$0.11–0.13/h on-demand ≈ **$80–95/mo** 24/7 ([computeprices, Aug 2026](https://computeprices.com/providers/vast/gpus/rtx3090)) | Yes (tight: ~21 GB weights plus a few GB of KV) | Peer-to-peer hosts, so data sits on a third party's machine. Availability varies. |
| **Vast.ai RTX 4090** | 24 GB | ~$0.27/h ≈ **$197/mo** ([gpu-hosting.org](https://gpu-hosting.org/cheap-gpu-hosting/)) | Yes | Same caveat as above. |
| RunPod Community RTX 3090 / 4090 | 24 GB | $0.22/h ≈ $160 (3090); $0.34/h ≈ $248 (4090, [official page, Jul 2026](https://www.runpod.io/gpu-cloud/pricing)) | Yes | The 4090 is over budget. Secure Cloud costs 20–30% more. |
| CloudClusters RTX A4000 (dedicated) | 16 GB | $179/mo ([link](https://www.cloudclusters.io/server/gpu)) | No (Qwen3.5-9B / Gemma 4 26B-A4B at Q3–Q4 only) | Dedicated, but a smaller card. |
| Hetzner GEX45 (dedicated, Germany) | RTX PRO 4000 Blackwell 24 GB | €214/mo + €209 setup ([WZ-IT, 13 Oct 2026](https://wz-it.com/blog/hetzner-gpu-server-vergleich/)) | Yes | **Slightly over $200** (about $250 **[unverified FX]**). It is the best "real" dedicated option if the budget can stretch. |
| HOSTKEY RTX 3090 (dedicated) | 24 GB | €209–299/mo ([link](https://hostkey.com/gpu-dedicated-servers/)) | Yes | Over budget. |
| CPU-only big-RAM box | — | — | Fits in RAM | **Not viable.** Prompt processing on CPU is about 50–150 tok/s, so a 3k-token prompt takes 20–60 s per call and breaks the 40 s budget **[estimate]**. |
| Contabo / OVH / Hostinger GPU | — | No current sub-$200 24 GB offer found | — | **[unverified]** |

- **Privacy note:** marketplace GPUs (Vast, RunPod Community) process prompts on third-party hardware. That is acceptable for fictional demo data. It is not acceptable for real customer files without a review, which is the same class of concern as today's hosted DeepSeek.

### 4.3 Expected speed for our pattern (~3k-token prompt, JSON output)

Estimates scale public llama.cpp reports by memory bandwidth. **All are [unverified] until `llama-bench` is run on the actual box.**

| Setup | Prefill | Decode | One call (3k in / 300 out) | One call (3k in / 1k out) | A 1–3 call question |
|---|---|---|---|---|---|
| Qwen3.6-35B-A3B Q4_K_M, RTX 3090/4090 | ~1.5–3k tok/s | ~90–130 tok/s ([30 tok/s even with all experts on CPU](https://lemmy.4d2.org/comment/6479265)) | **~3–5 s** | ~9–12 s | ~4–20 s |
| Qwen3.6-27B Q4_K_M, RTX 3090/4090 | ~1k tok/s | ~30–40 tok/s ([16 GB VRAM tests](https://glukhov.org/llm-performance/benchmarks/best-llm-on-16gb-vram-gpu/)) | ~11 s | ~30 s | 12–60 s (risks the 40 s budget) |
| Qwen3.5-9B Q4_K_M, current P100 | ~400–700 tok/s | ~25–35 tok/s | ~12–17 s | ~35–45 s (over budget, so cap at ≤512) | 15–50 s |
| Qwen3.6-35B-A3B, P100 + AVX-only CPU experts | slow | ~3–8 tok/s | 40 s+ | — | Not viable |

## 5. Serving

- **llama.cpp `llama-server` (recommended):**
  - It serves an OpenAI-compatible `/v1/chat/completions`.
  - `response_format` in both `json_object` and `json_schema` form is turned into a grammar, which gives constrained decoding.
  - `--jinja` uses the model's chat template.
  - Thinking can be disabled **server-side** with `--chat-template-kwargs '{"enable_thinking":false}'` or `--reasoning-budget 0`. Our adapter only sends `reasoning_effort`, so this matters. Verify which flag the installed build accepts **[unverified per version]**.
  - `--parallel 2–4` with a per-slot context of 8–16k suits a few concurrent users.
  - It runs on Pascal and newer.
- **Ollama:** this is what the VPS already runs (0.20.0). It is easiest for the fallback.
  - Its `qwen3.5` registry tags partly route to Ollama Cloud ([registry](https://registry.ollama.ai/library/qwen3.5)). **Import a local GGUF instead, and never use a `:cloud` tag.** Otherwise data leaves the box.
  - Ollama 0.20.0's support for the Qwen3.5/3.6 Gated-DeltaNet architecture was not confirmed **[unverified]**. An upgrade may be needed.
- **vLLM:** best throughput and guided JSON decoding, and it is officially recommended by Qwen (≥0.19).
  - It needs an Ampere-or-newer GPU, so it does not work on the P100.
  - An AWQ/GPTQ 4-bit 35B-A3B fits 24 GB tightly.
  - For a few users it is not worth the extra operating work. Revisit at production scale.
- **Integration (expected zero code change):**
  - `bootstrap.py` builds provider-neutral OpenAI-compatible adapters from settings.
  - Set the following:
    - `EXECPLUS_LLM_MODE=local`
    - `EXECPLUS_LLM_BASE_URL=http://<gpu-host-tunnel>:<port>/v1`
    - `EXECPLUS_LLM_SMALL_MODEL` = `EXECPLUS_LLM_LARGE_MODEL` = `qwen3.6-35b-a3b`
    - `EXECPLUS_LLM_JSON_MODE=true`
    - `EXECPLUS_LLM_SELECTION_BASE_URL` / `MODEL` pointing at the same endpoint (Option A), or left empty if the selector is dropped.
  - Leave `EXECPLUS_LLM_REASONING_EFFORT` unset unless the server maps it.
  - Reach the rented box over an SSH tunnel or WireGuard, binding the server to loopback, as with today's six loopback listeners.
- **Possible small code change (only if needed):** if a server cannot disable thinking by default, the adapter would need to pass `chat_template_kwargs`. Today it only sends `response_format` and `reasoning_effort` (`openai_compatible.py:69–73`).

## 6. Recommendation, fallback and expected quality

- **Primary:**
  - **Model:** Qwen3.6-35B-A3B Q4_K_M (unsloth or bartowski GGUF).
  - **Server:** `llama-server --jinja`, thinking off, JSON grammar on.
  - **Hardware:** one 24 GB RTX 3090/4090 on a monthly marketplace rental, about $80–200/mo.
  - **Architecture:** Option A, one model for every route.
  - **Second candidate in the same bake-off:** Gemma 4 26B-A4B. It is similar in size and speed and may be better at Urdu.
- **Fallback (no extra cost):** Qwen3.5-9B Q4_K_M on the current P100 via Ollama or llama.cpp, with a local GGUF.
  - It replaces both Qwen3-4B and DeepSeek.
  - Cap output at about 512 tokens for plans.
  - Expect lower narrative and Roman Urdu quality and 15–50 s questions.
- **Expected quality against DeepSeek V4 Pro (honest):**
  - **Route, column and plan JSON:** likely 0–10 points lower on our structured cases. The grammar and server validators remove malformed output, and the remaining errors become clarifications, not wrong numbers.
  - **Explanations and readings:** shorter and plainer, with occasional awkward phrasing. Claim filters still block invented numbers.
  - **Roman Urdu and Urdu:** the biggest unknown. Test it before committing.
  - **Long schemas:** 100+ columns could exceed per-slot context. The planner schema is not token-packed today, so watch for truncation.
  - Numbers stay exactly right in every option, because the model never computes them.

## 7. Migration and evaluation plan, with go/no-go thresholds

1. **Rent and benchmark (1 day).**
   - Rent a 24 GB box for 1–2 days, which costs a few dollars on an hourly plan.
   - Run `llama-bench` for the 35B-A3B and Gemma 4 26B-A4B models at a 3k prompt.
   - Record prefill and decode speeds.
   - On the VPS, run the same test for Qwen3.5-9B on the P100.
2. **Same-day baseline.** Run every evaluation below against today's DeepSeek configuration, so the comparison is fair.
3. **Offline evaluations against each candidate endpoint** (point `.env` or the evaluation settings at the candidate; 3 repeats each):
   - `make evaluate-demo-model`: 20 document evidence-selection cases in strict JSON. Note that it tests JSON discipline and evidence choice only, **not dataset planning**.
   - `scripts/run_agent_harness_evaluation.py --mode hosted_synthetic` against the 20-case frozen corpus `docs/agent-harness-evaluation-corpus.json`. It scores intent, tools, required filters, expected values and forbidden claims. This is the key planner test.
   - `scripts/check_analysis_evaluation.py` and the live question sets used in the October 17–21 releases: the four hosted natural-language tasks, the seven reported-style turns, and the 7/7 chat check including Roman Urdu.
   - **New, small:** 15–20 Roman Urdu and Urdu questions over the demo datasets, scored the same way. This set does not exist yet and needs to be written.
   - Phase 3D's 12 judge cases in the closed-form verifier mode, only if Option C is being considered.
4. **Go/no-go thresholds** (proposed; the owner should confirm):
   - **JSON validity:** 100%, because the grammar guarantees it. Any parse failure is a no-go.
   - **Agent-harness corpus:** within 1 case of DeepSeek on intent, tool and filter matches, with **zero** wrong executed values and zero forbidden claims.
   - **Evidence selection** (`evaluate-demo-model`): at least DeepSeek's score minus 1 out of 20.
   - **Roman Urdu set:** at least 80% correct route or plan, against DeepSeek's score on the same set.
   - **Latency:** p95 per question under 25 s, no 40 s budget timeouts, and fallback rate no higher than DeepSeek's.
   - **Human blind review** of 10 explanations: rated "acceptable" in at least 8 of 10.
   - **Result:**
     - If every threshold passes: go.
     - If the planner passes but explanations fail: run the open model for planning, and keep DeepSeek only for readings temporarily. This is a partial go and does not meet the "replace entirely" goal.
     - Anything else: no-go.
5. **Cut over (private demo).**
   - Take a checked backup.
   - Change only the `.env` model routes, with no schema change.
   - Run the live smoke test with fictional accounts and revoke them afterwards.
   - Keep the DeepSeek key configured for a one-line rollback.
6. **Drop the separate selector** if Option A matches Option B on the harness corpus. That removes one serial call.

## 8. Not verified / limits

- Every tok/s and latency figure is an estimate until benchmarked on the real hardware.
- No source confirms Ollama 0.20.0, or llama.cpp CUDA on Pascal, running the Qwen3.5/3.6 Gated-DeltaNet architecture.
- I could not verify from the allowed commands whether the current Qwen3-4B runs on the GPU or the CPU.
- No Urdu or Roman Urdu benchmark exists for these models.
- Most benchmark figures are vendor-reported. The official BFCL and BIRD leaderboards were not read directly.
- Marketplace prices change daily. The currency conversion is approximate.
- The Qwen3.6-27B release date conflicts between sources (April on Hugging Face, October 21 on one tracker).
- Rental hosts' data handling has not been reviewed.
