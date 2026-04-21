import { Elysia, t } from "elysia";
import { authResolver } from "../middleware/authResolver";
import { rateLimitMiddleware } from "../middleware/rateLimiter";
import logger from "../utils/logger";
import { valichordValidatorAgent } from "../agents/valichord";
import type { ValiChordDiscipline } from "../agents/valichord/types";

/**
 * ValiChord Validator Route
 *
 * Exposes BioAgents as an AI validator in the ValiChord reproducibility protocol.
 * Downloads a research deposit, reproduces the analysis, and submits an attestation.
 *
 * POST /api/valichord/validate
 *   Body: { depositUrl, discipline?, studyDescription? }
 *   Returns: ValiChordAttestationResult
 */
export const valichordRoute = new Elysia().guard(
  {
    beforeHandle: [
      authResolver({ required: true }),
      rateLimitMiddleware("chat"),
    ],
  },
  (app) =>
    app.post(
      "/api/valichord/validate",
      async ({ body, set }) => {
        const { depositUrl, discipline, studyDescription } = body;

        logger.info(
          { depositUrl, discipline, studyDescription },
          "valichord_validate_request",
        );

        try {
          const result = await valichordValidatorAgent({
            depositUrl,
            discipline: discipline as ValiChordDiscipline | undefined,
            studyDescription: studyDescription ?? undefined,
          });

          return result;
        } catch (err) {
          logger.error({ err }, "valichord_validate_failed");
          set.status = 500;
          return {
            error:
              err instanceof Error
                ? err.message
                : "ValiChord validation failed",
          };
        }
      },
      {
        body: t.Object({
          depositUrl: t.String({
            description: "URL of the research deposit ZIP to validate",
          }),
          discipline: t.Optional(
            t.Object(
              {
                type: t.String({
                  description:
                    "Discipline variant: ComputationalBiology, ClimateScience, SocialScience, " +
                    "Economics, Psychology, Neuroscience, MachineLearning, or Other",
                }),
                content: t.Optional(
                  t.String({ description: 'Description when type is "Other"' }),
                ),
              },
              {
                description:
                  'Discipline JSON, e.g. {"type":"ComputationalBiology"}. Defaults to ComputationalBiology.',
              },
            ),
          ),
          studyDescription: t.Optional(
            t.String({
              description:
                "Brief description of the study and its key claims (optional — inferred from README if omitted)",
            }),
          ),
        }),
      },
    ),
);
