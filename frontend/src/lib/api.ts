import type {
  EligibilityResponse,
  RunwayRequest,
  RunwayResponse,
  EvidenceContext,
  EvidenceExtractionResponse,
  PacketBuildRequest,
  PacketBuildResponse,
  PacketFileEntry,
  PlanGenerateRequest,
  PlanResponse,
  ResultsSummary,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(body.detail || "An unexpected error occurred", response.status);
  }
  return response.json();
}

// ── Eligibility ──────────────────────────────────────────────

export async function lookupEligibility(
  county: string,
  state: string
): Promise<EligibilityResponse> {
  const res = await fetch(`${API_BASE}/eligibility/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ county, state }),
  });
  return handleResponse<EligibilityResponse>(res);
}

// ── Runway ───────────────────────────────────────────────────

export async function calculateRunway(
  data: RunwayRequest
): Promise<RunwayResponse> {
  const res = await fetch(`${API_BASE}/runway/calc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<RunwayResponse>(res);
}

// ── Evidence Extraction ──────────────────────────────────────

export async function extractEvidence(
  files: File[],
  context: EvidenceContext
): Promise<EvidenceExtractionResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("context", JSON.stringify(context));

  const res = await fetch(`${API_BASE}/ai/evidence/extract`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<EvidenceExtractionResponse>(res);
}

// ── Packet Build ─────────────────────────────────────────────

export interface BuildPacketResult {
  blob: Blob;
  filename: string;
  resultsSummary: ResultsSummary;
  filesIncluded: PacketFileEntry[];
}

async function base64ToBlob(base64: string, mimeType: string): Promise<Blob> {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mimeType });
}

export async function buildPacket(
  data: PacketBuildRequest
): Promise<BuildPacketResult> {
  const res = await fetch(`${API_BASE}/packet/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new ApiError(
      json.detail || "Failed to build packet",
      res.status
    );
  }
  const payload = json as PacketBuildResponse;
  const blob = await base64ToBlob(payload.zip_base64, "application/zip");
  return {
    blob,
    filename: payload.filename,
    resultsSummary: payload.results_summary,
    filesIncluded: payload.files_included,
  };
}

// ── Plan Generate ────────────────────────────────────────────

export async function generatePlan(
  data: PlanGenerateRequest
): Promise<PlanResponse> {
  const res = await fetch(`${API_BASE}/plan/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return handleResponse<PlanResponse>(res);
}
