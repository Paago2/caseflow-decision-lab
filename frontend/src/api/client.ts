export type UnderwritePayload = {
  credit_score: number;
  monthly_income: number;
  monthly_debt: number;
  loan_amount: number;
  property_value: number;
  occupancy: "primary" | "secondary" | "investment";
};

export type Citation = {
  document_id: string;
  chunk_id: string;
  start_char: number;
  end_char: number;
  score: number;
};

export type UnderwriteResponse = {
  schema_version: string;
  case_id: string;
  decision: string;
  risk_score: number;
  policy: {
    policy_id: string;
    decision: string;
    reasons: string[];
    derived: Record<string, number>;
  };
  justification: {
    summary: string;
    reasons: string[];
    citations: Citation[];
  };
  request_id: string;
};

export type TraceNode = {
  node_name: string;
  duration_ms: number;
};

type ApiErrorEnvelope = {
  error?: { message?: string };
  detail?: string;
  message?: string;
};

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() || "/api";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  const text = await response.text();
  const parsed: unknown = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const payload = (parsed ?? {}) as ApiErrorEnvelope;
    const message =
      payload.error?.message ||
      payload.detail ||
      payload.message ||
      `HTTP ${response.status}`;
    throw new Error(message);
  }

  return parsed as T;
}

export async function ocrExtract(
  case_id: string,
  filename: string,
  content_type: string,
  content_b64: string,
) {
  return requestJson<{
    case_id: string;
    document_id: string;
    request_id: string;
  }>("/ocr/extract", {
    method: "POST",
    body: JSON.stringify({
      case_id,
      document: { filename, content_type, content_b64 },
    }),
  });
}

export async function evidenceIndex(
  case_id: string,
  document_id: string,
  overwrite: boolean,
) {
  return requestJson(`/mortgage/${case_id}/evidence/index`, {
    method: "POST",
    body: JSON.stringify({ documents: [{ document_id }], overwrite }),
  });
}

export async function underwrite(
  case_id: string,
  payload: UnderwritePayload,
  model_version: string,
  top_k: number,
) {
  return requestJson<UnderwriteResponse>(`/mortgage/${case_id}/underwrite`, {
    method: "POST",
    body: JSON.stringify({ payload, model_version, top_k }),
  });
}

export async function getTrace(case_id: string, request_id: string) {
  const response = await requestJson<{
    trace: { trace?: Array<{ node_name?: string; duration_ms?: number }> };
  }>(
    `/mortgage/${case_id}/underwrite/trace?request_id=${encodeURIComponent(
      request_id,
    )}`,
  );
  const timeline = response.trace.trace ?? [];
  return timeline.map((node) => ({
    node_name: node.node_name ?? "unknown",
    duration_ms: Number(node.duration_ms ?? 0),
  }));
}

export async function replay(case_id: string, request_id: string) {
  return requestJson<UnderwriteResponse>(
    `/mortgage/${case_id}/underwrite/replay?request_id=${encodeURIComponent(
      request_id,
    )}`,
    { method: "POST" },
  );
}
