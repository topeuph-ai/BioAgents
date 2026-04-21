import type { ValiChordDiscipline } from "./types";

export function buildValidationPrompt(
  depositUrl: string,
  discipline: ValiChordDiscipline,
  studyDescription: string,
): string {
  const disciplineJson = JSON.stringify(discipline);

  return `You are acting as an AI validator in the ValiChord reproducibility protocol.
Your task: download the research deposit at the URL below, inspect it, attempt to
reproduce the key findings, and submit a cryptographically-committed attestation.

**Deposit URL:** ${depositUrl}
**Discipline:** ${disciplineJson}
**Study description:** ${studyDescription || "Not provided — infer from the deposit README."}

Use the valichord-validator skill to complete this task end-to-end:

1. Download and hash the deposit (--mode download-and-hash)
2. Inspect its contents (--mode inspect)
3. Read the README and main analysis scripts
4. Attempt to reproduce the key findings; record what matched and what did not
5. Submit your attestation (--mode submit-attestation) with:
   - --data-hash  <computed above>
   - --outcome    Reproduced | PartiallyReproduced | FailedToReproduce
   - --confidence High | Medium | Low
   - --discipline '${disciplineJson}'
   - --notes      <detailed replication notes, max 2000 chars>

Be honest: a FailedToReproduce with High confidence is more valuable than a
spurious Reproduced. "Reproduced" means you obtained the same result as the
researcher — not that the result is correct.

After submitting, report the full attestation result JSON.`;
}
