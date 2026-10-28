export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";
export type ReviewAction = "approve" | "override" | "rerun";

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
}

export interface ReadinessCheck {
  name: string;
  ok: boolean;
  detail?: string | null;
}

export interface ReadinessResponse {
  status: "ready" | "degraded";
  checks: ReadinessCheck[];
}

export interface DocumentSummary {
  hash: string;
  filename: string | null;
  status: string | null;
  ingested_at: string | null;
  entity_count: number | null;
  relationship_count: number | null;
  failed_batch_count: number | null;
}

export interface CompanySummary {
  id: string;
  name: string | null;
  description: string | null;
  relationship_count: number;
  assessment_count: number;
}

export interface ReviewEvent {
  id: string | null;
  at: string | null;
  action: string | null;
  reviewer: string | null;
  iteration: number | null;
  notes: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
}

export interface AssessmentRecord {
  id: string;
  risk_level: string | null;
  final_risk_level: string | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  net_margin: number | null;
  final_debt_to_equity: number | null;
  final_current_ratio: number | null;
  final_net_margin: number | null;
  status: string | null;
  notes: string[];
  final_notes: string[];
  created_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  overridden: boolean | null;
  edit_notes: string | null;
  review_count: number | null;
  document_hash: string | null;
  document_filename: string | null;
  review_events: ReviewEvent[];
}

export interface DashboardResponse {
  company: CompanySummary;
  latest_assessment: AssessmentRecord | null;
  assessments: AssessmentRecord[];
  documents: DocumentSummary[];
  totals: Record<string, number>;
}

export interface GraphNode {
  id: string;
  name: string | null;
  type: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string | null;
  detail: string | null;
}

export interface GraphResponse {
  company_id: string;
  depth: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  truncated: boolean;
}

export interface UploadResponse {
  job_id: string;
  status: string;
  filename: string;
  size_bytes: number;
  document_hash: string;
  persistent: boolean;
  message: string;
}

export type BatchStatus = "pending" | "running" | "cached" | "completed" | "failed";

export interface BatchProgress {
  index: number;
  status: BatchStatus;
  entities: number | null;
  cached: boolean;
  error: string | null;
}

export interface JobResponse {
  job_id: string;
  status: string;
  stage: string;
  filename: string;
  document_hash: string;
  created_at: string;
  updated_at: string;
  batch_total: number;
  batches: BatchProgress[];
  document: DocumentSummary | null;
  error: string | null;
  persistent: boolean;
}

export interface DeleteDocumentResponse {
  document_hash: string;
  filename: string | null;
  deleted_entities: number;
  deleted_relationships: number;
  deleted_assessments: number;
  deleted_points: number;
  upload_removed: boolean;
}

export interface ReviewPayload {
  company_name: string;
  auditor_findings: string[];
  risk_score: Record<string, unknown>;
  final_score: Record<string, unknown> | null;
  quant_context: Record<string, unknown> | null;
  iteration: number;
  reruns_left: number;
  review_history: Record<string, unknown>[];
}

export interface AnalysisResponse {
  analysis_id: string;
  status: "awaiting_review" | "completed" | "failed" | "running";
  company_id: string;
  company_name: string;
  document_hash: string;
  document_filename: string | null;
  reviewer: string;
  iteration: number;
  max_iterations: number;
  review: ReviewPayload | null;
  approval_record: Record<string, unknown> | null;
  report_url: string | null;
  error: string | null;
  persistent: boolean;
}

export interface ReviewRequest {
  action: ReviewAction;
  notes?: string;
  edited_score?: Record<string, number | null>;
  risk_level?: RiskLevel | null;
}

export interface EvidenceHit {
  text: string;
  filename: string | null;
  score: number;
}

export interface EvidenceSearchResponse {
  document_hash: string;
  query: string;
  results: EvidenceHit[];
}

export interface AskResponse {
  document_hash: string;
  question: string;
  answer: string;
}
