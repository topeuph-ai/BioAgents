export type ValiChordOutcome =
  | "Reproduced"
  | "PartiallyReproduced"
  | "FailedToReproduce";

export type ValiChordConfidence = "High" | "Medium" | "Low";

export type ValiChordDiscipline =
  | { type: "ComputationalBiology" }
  | { type: "ClimateScience" }
  | { type: "SocialScience" }
  | { type: "Economics" }
  | { type: "Psychology" }
  | { type: "Neuroscience" }
  | { type: "MachineLearning" }
  | { type: "Other"; content: string };

export type ValiChordAttestationInput = {
  depositUrl: string;
  discipline?: ValiChordDiscipline;
  studyDescription?: string;
};

export type ValiChordAttestationResult = {
  data_hash: string;
  outcome: ValiChordOutcome;
  confidence: ValiChordConfidence;
  notes: string;
  validator_attested: boolean;
  harmony_record_hash: string | null;
  harmony_record_url: string | null;
  start: string;
  end: string;
};
