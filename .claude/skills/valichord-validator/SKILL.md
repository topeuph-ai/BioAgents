---
name: valichord-validator
description: This skill should be used when asked to validate, attest, or reproduce a research deposit for ValiChord. Triggers on phrases like "validate this deposit", "attest to this study", "reproduce this analysis", or "submit to ValiChord". Requires a deposit URL or data hash and an explicit outcome decision.
---

# ValiChord Validator Skill

## Purpose

This skill enables BioAgents to act as an AI validator in the ValiChord reproducibility
protocol. Given a research deposit (ZIP URL or local path), it analyses the deposit,
attempts to reproduce key findings, and submits a cryptographically-committed attestation
to the ValiChord peer network via the bridge API.

**ValiChord is NOT a blockchain.** It is an agent-centric distributed network where each
node maintains its own signed source chain. "Reproduced" means the validator arrived at
the same result as the researcher — not that the result is correct.

## When to Use This Skill

Use this skill when asked to:
- Validate or attest to a research deposit
- Reproduce a study's analysis for ValiChord
- Submit a replication verdict (Reproduced / PartiallyReproduced / FailedToReproduce)
- Check whether a deposit can be independently reproduced

**Trigger phrases:**
- "Validate this deposit for ValiChord"
- "Attest to this study"
- "Reproduce this analysis"
- "Submit replication verdict to ValiChord"
- "Can you reproduce these results?"

**Do NOT trigger** on general questions about reproducibility that don't request a
concrete attestation submission.

## Attestation Outcomes

| Outcome | Meaning |
|---|---|
| `Reproduced` | Validator obtained the same result as the researcher |
| `PartiallyReproduced` | Key results matched but secondary findings diverged |
| `FailedToReproduce` | Validator could not obtain the same result |

**Important:** Reproduced ≠ correct. A study can be reproducible and scientifically wrong.
ValiChord only answers: *can an independent party arrive at the same result?*

## How to Use This Skill

### Step 1: Gather Deposit Information

Parse the user's request to identify:
1. **Deposit source** — URL to download from, or local file path, or a 64-char hex SHA-256
2. **Discipline** — one of: `ComputationalBiology`, `ClimateScience`, `SocialScience`,
   `Economics`, `Psychology`, `Neuroscience`, `MachineLearning`
3. **Study description** — what the research claims to show

### Step 2: Download and Hash the Deposit

If a URL is provided (not already a hash), download and compute the SHA-256:

```bash
python3 scripts/valichord_bridge.py \
  --mode download-and-hash \
  --url "https://example.com/deposit.zip"
```

The script outputs JSON: `{ "data_hash": "<64-char hex>", "local_path": "<path>" }`

If a local path is provided instead of a URL, pass `--file` instead of `--url`:
```bash
python3 scripts/valichord_bridge.py \
  --mode download-and-hash \
  --file "/path/to/deposit.zip"
```

### Step 3: Inspect Deposit Contents

After download, list and inspect the deposit:

```bash
python3 scripts/valichord_bridge.py \
  --mode inspect \
  --file "<local_path from Step 2>"
```

This lists all files in the deposit and returns a summary of:
- Entry point scripts (main analysis scripts)
- Data files
- README / documentation
- Environment / requirements files

### Step 4: Analyse and Attempt Reproduction

Read the key files identified in Step 3:
- Read the README to understand the study's claims
- Read the main analysis scripts to understand the methodology
- Use the `Read` and `Grep` tools to inspect code and data

For each key claim in the README:
1. Identify the analysis step that produces it
2. Check whether the code is self-contained and runnable
3. Note any missing dependencies, hardcoded paths, or missing data

If the deposit is small enough and the environment is available, attempt to run the
analysis with `Bash`. Record exact outputs.

Form an honest verdict:
- **Reproduced**: You ran the code and got the same result, OR the code is obviously
  correct, complete, and deterministic with matching outputs
- **PartiallyReproduced**: Some results match but not all, OR the code ran with warnings
  or minor discrepancies
- **FailedToReproduce**: Code failed to run, missing data/dependencies, or results
  did not match the claimed findings

Confidence levels:
- **High**: You actually ran the code and verified outputs match
- **Medium**: You inspected the code thoroughly but could not fully execute it
- **Low**: You could only inspect the deposit superficially

### Step 5: Submit Attestation

Submit your verdict using the bridge script:

```bash
python3 scripts/valichord_bridge.py \
  --mode submit-attestation \
  --api-url "$VALICHORD_API_URL" \
  --api-key "$VALICHORD_API_KEY" \
  --data-hash "<64-char hex from Step 2>" \
  --outcome "Reproduced" \
  --confidence "High" \
  --discipline '{"type":"ComputationalBiology"}' \
  --notes "Ran main_analysis.R; output table matched Table 2 exactly. All 47 p-values reproduced within floating point tolerance."
```

**Notes guidelines (max 2000 chars):**
- Describe exactly what you ran and what you observed
- Quote key output values and compare them to the paper's claims
- State clearly what matched and what did not
- If reproduction failed, state the exact error or discrepancy

The script returns JSON:
```json
{
  "data_hash": "...",
  "outcome": "Reproduced",
  "validator_attested": true,
  "harmony_record_hash": "uhCkk...",
  "harmony_record_url": "https://..."
}
```

`harmony_record_hash` is null when the Holochain conductor is offline; the attestation
is still recorded locally.

### Step 6: Present Result

Report the attestation outcome to the user in a clear, honest summary:

```
ValiChord Attestation Submitted
================================
Deposit hash:  <64-char hex>
Outcome:       Reproduced | PartiallyReproduced | FailedToReproduce
Confidence:    High | Medium | Low
HarmonyRecord: <hash or "conductor offline">

Summary: [2-3 sentences describing what was tested and what was found]

Notes submitted:
[Full notes text]
```

## Discipline JSON Reference

Pass the `--discipline` flag as a JSON object matching the `Discipline` enum:

| Study type | JSON |
|---|---|
| Computational biology / bioinformatics | `{"type":"ComputationalBiology"}` |
| Climate science / environmental | `{"type":"ClimateScience"}` |
| Social science | `{"type":"SocialScience"}` |
| Economics | `{"type":"Economics"}` |
| Psychology / behavioural | `{"type":"Psychology"}` |
| Neuroscience | `{"type":"Neuroscience"}` |
| Machine learning / AI | `{"type":"MachineLearning"}` |
| Other | `{"type":"Other","content":"<description>"}` |

## Script Reference

The skill includes `scripts/valichord_bridge.py` which provides four modes:

| Mode | Purpose |
|---|---|
| `download-and-hash` | Download deposit URL or hash local file; returns `data_hash` + `local_path` |
| `inspect` | List files in a deposit ZIP and classify by type |
| `submit-attestation` | POST to `/attest`; returns HarmonyRecord result |
| `get-result` | Poll `GET /result/<job_id>` for a submitted deposit job |

Run `python3 scripts/valichord_bridge.py --help` for full parameter documentation.

## Important Notes

- **Never fabricate a hash** — always compute it from the actual deposit bytes
- **Be honest** — a FailedToReproduce with High confidence is more valuable than a
  spurious Reproduced
- **The conductor may be offline** — this is expected in development; `harmony_record_hash`
  will be null but the attestation intent is still returned
- **VALICHORD_API_URL defaults to `http://localhost:5000`** if not set
- **VALICHORD_API_KEY** is optional for local development instances
