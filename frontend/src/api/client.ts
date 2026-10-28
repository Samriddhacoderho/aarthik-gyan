import type {
  AnalysisResponse,
  AskResponse,
  CompanySummary,
  DashboardResponse,
  DeleteDocumentResponse,
  DocumentSummary,
  EvidenceSearchResponse,
  GraphResponse,
  HealthResponse,
  JobResponse,
  ReadinessResponse,
  ReviewRequest,
  UploadResponse,
} from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

export class ApiRequestError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function apiUrl(path: string): string {
  return `${BASE}${path}`;
}

async function parseError(response: Response): Promise<ApiRequestError> {
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string; details?: unknown };
    };
    return new ApiRequestError(
      response.status,
      body.error?.code ?? "request_failed",
      body.error?.message ?? `Request failed with HTTP ${response.status}.`,
      body.error?.details,
    );
  } catch {
    return new ApiRequestError(
      response.status,
      "request_failed",
      `Request failed with HTTP ${response.status}.`,
    );
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...init, headers });
  } catch {
    throw new ApiRequestError(
      0,
      "network_error",
      "The service is unreachable. Check your connection and try again.",
    );
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export const api = {
  live: () => request<HealthResponse>("/health/live"),
  ready: async (): Promise<ReadinessResponse> => {
    // Readiness deliberately returns HTTP 503 while degraded, but still carries
    // a useful checks payload. Parse that payload instead of treating it as a
    // generic request failure.
    const response = await fetch(apiUrl("/health/ready"));
    const body = (await response.json()) as ReadinessResponse & {
      error?: { code?: string; message?: string };
    };
    if (Array.isArray(body.checks)) return body;
    throw new ApiRequestError(
      response.status,
      body.error?.code ?? "readiness_failed",
      body.error?.message ?? "Readiness check failed.",
    );
  },

  documents: () => request<DocumentSummary[]>("/documents"),
  document: (hash: string) => request<DocumentSummary>(`/documents/${encodeURIComponent(hash)}`),
  deleteDocument: (hash: string) =>
    request<DeleteDocumentResponse>(`/documents/${encodeURIComponent(hash)}`, {
      method: "DELETE",
    }),
  retryDocument: (hash: string) =>
    request<JobResponse>(`/documents/${encodeURIComponent(hash)}/retry`, {
      method: "POST",
    }),
  documentCompanies: (hash: string) =>
    request<CompanySummary[]>(`/documents/${encodeURIComponent(hash)}/companies`),
  evidence: (hash: string, query: string, topK = 5) => {
    const params = new URLSearchParams({ query, top_k: String(topK) });
    return request<EvidenceSearchResponse>(
      `/documents/${encodeURIComponent(hash)}/search?${params.toString()}`,
    );
  },
  askDocument: (hash: string, question: string) =>
    request<AskResponse>(`/documents/${encodeURIComponent(hash)}/ask`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  jobs: () => request<JobResponse[]>("/jobs"),
  job: (jobId: string) => request<JobResponse>(`/jobs/${encodeURIComponent(jobId)}`),

  companies: () => request<CompanySummary[]>("/companies"),
  company: (companyId: string) =>
    request<CompanySummary>(`/companies/${encodeURIComponent(companyId)}`),
  dashboard: (companyId: string) =>
    request<DashboardResponse>(`/companies/${encodeURIComponent(companyId)}/dashboard`),
  graph: (companyId: string, depth = 1) =>
    request<GraphResponse>(
      `/companies/${encodeURIComponent(companyId)}/graph?depth=${depth}`,
    ),

  analyses: () => request<AnalysisResponse[]>("/analyses"),
  analysis: (analysisId: string) =>
    request<AnalysisResponse>(`/analyses/${encodeURIComponent(analysisId)}`),
  startAnalysis: (payload: {
    company_id: string;
    document_hash: string;
    reviewer: string;
    max_iterations?: number;
  }) =>
    request<AnalysisResponse>("/analyses", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  reviewAnalysis: (analysisId: string, payload: ReviewRequest) =>
    request<AnalysisResponse>(`/analyses/${encodeURIComponent(analysisId)}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  uploadDocument: (file: File, onProgress?: (percent: number) => void) =>
    new Promise<UploadResponse>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", apiUrl("/documents"));
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onerror = () =>
        reject(new ApiRequestError(0, "network_error", "Upload failed: service unreachable."));
      xhr.onload = () => {
        try {
          const body = JSON.parse(xhr.responseText || "{}") as UploadResponse & {
            error?: { code?: string; message?: string; details?: unknown };
          };
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(body);
          } else {
            reject(
              new ApiRequestError(
                xhr.status,
                body.error?.code ?? "upload_failed",
                body.error?.message ?? "Upload failed.",
                body.error?.details,
              ),
            );
          }
        } catch {
          reject(new ApiRequestError(xhr.status, "upload_failed", "Upload failed."));
        }
      };
      const form = new FormData();
      form.append("file", file);
      xhr.send(form);
    }),

  reportUrl: (analysisId: string) =>
    apiUrl(`/analyses/${encodeURIComponent(analysisId)}/report`),
};
