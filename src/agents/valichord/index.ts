import logger from "../../utils/logger";
import { callAnthropicWithSkills } from "../../llm/skills/skills";
import { buildValidationPrompt } from "./prompts";
import type {
  ValiChordAttestationInput,
  ValiChordAttestationResult,
  ValiChordConfidence,
  ValiChordDiscipline,
  ValiChordOutcome,
} from "./types";

const OUTCOME_VALUES = new Set<ValiChordOutcome>([
  "Reproduced",
  "PartiallyReproduced",
  "FailedToReproduce",
]);

const CONFIDENCE_VALUES = new Set<ValiChordConfidence>(["High", "Medium", "Low"]);

function parseAttestationFromResult(text: string): {
  outcome: ValiChordOutcome;
  confidence: ValiChordConfidence;
  notes: string;
  data_hash: string;
  harmony_record_hash: string | null;
  harmony_record_url: string | null;
  validator_attested: boolean;
} | null {
  // Try to find a JSON block containing the attestation result
  const jsonMatches = text.matchAll(/\{[^{}]*"outcome"\s*:\s*"[^"]*"[^{}]*\}/gs);
  for (const match of jsonMatches) {
    try {
      const obj = JSON.parse(match[0]);
      if (obj.outcome && OUTCOME_VALUES.has(obj.outcome as ValiChordOutcome)) {
        return {
          outcome: obj.outcome as ValiChordOutcome,
          confidence: CONFIDENCE_VALUES.has(obj.confidence as ValiChordConfidence)
            ? (obj.confidence as ValiChordConfidence)
            : "Medium",
          notes: typeof obj.notes === "string" ? obj.notes : "",
          data_hash: typeof obj.data_hash === "string" ? obj.data_hash : "",
          harmony_record_hash:
            typeof obj.harmony_record_hash === "string"
              ? obj.harmony_record_hash
              : null,
          harmony_record_url:
            typeof obj.harmony_record_url === "string"
              ? obj.harmony_record_url
              : null,
          validator_attested: obj.validator_attested === true,
        };
      }
    } catch {
      // Not valid JSON, try next match
    }
  }

  // Fallback: extract outcome from free text
  let outcome: ValiChordOutcome = "FailedToReproduce";
  if (/\bReproduced\b/.test(text) && !/PartiallyReproduced/.test(text)) {
    outcome = "Reproduced";
  } else if (/PartiallyReproduced/.test(text)) {
    outcome = "PartiallyReproduced";
  }

  let confidence: ValiChordConfidence = "Low";
  if (/\bHigh\b/.test(text)) confidence = "High";
  else if (/\bMedium\b/.test(text)) confidence = "Medium";

  // Extract data_hash (64-char hex)
  const hashMatch = text.match(/\b([0-9a-f]{64})\b/);

  return {
    outcome,
    confidence,
    notes: text.slice(0, 2000),
    data_hash: hashMatch ? hashMatch[1] : "",
    harmony_record_hash: null,
    harmony_record_url: null,
    validator_attested: false,
  };
}

/**
 * ValiChord Validator Agent
 *
 * Downloads a research deposit, reproduces the analysis using BioAgents'
 * capabilities (via the valichord-validator Claude Code skill), and submits
 * a cryptographically-committed attestation to the ValiChord peer network.
 *
 * The attestation is honest: Reproduced means the same result was obtained —
 * not that the result is correct.
 */
export async function valichordValidatorAgent(
  input: ValiChordAttestationInput,
): Promise<ValiChordAttestationResult> {
  const {
    depositUrl,
    discipline = { type: "ComputationalBiology" } as ValiChordDiscipline,
    studyDescription = "",
  } = input;

  const start = new Date().toISOString();

  logger.info(
    { depositUrl, discipline, studyDescription },
    "valichord_validator_agent_started",
  );

  const prompt = buildValidationPrompt(depositUrl, discipline, studyDescription);

  const skillResult = await callAnthropicWithSkills(prompt);

  if (!skillResult || skillResult.is_error) {
    logger.error(
      { skillResult },
      "valichord_validator_agent_skill_failed",
    );
    throw new Error(
      `ValiChord validation skill failed: ${skillResult?.result ?? "no result returned"}`,
    );
  }

  const parsed = parseAttestationFromResult(skillResult.result);
  const end = new Date().toISOString();

  if (!parsed) {
    logger.error(
      { result: skillResult.result },
      "valichord_validator_agent_parse_failed",
    );
    throw new Error(
      "Could not parse attestation outcome from skill result. Check the skill logs.",
    );
  }

  logger.info(
    {
      outcome: parsed.outcome,
      confidence: parsed.confidence,
      data_hash: parsed.data_hash,
      harmony_record_hash: parsed.harmony_record_hash,
    },
    "valichord_validator_agent_completed",
  );

  return {
    ...parsed,
    start,
    end,
  };
}
