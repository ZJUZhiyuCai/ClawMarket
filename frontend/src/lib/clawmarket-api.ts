import { customFetch } from "@/api/mutator";
import { getApiBaseUrl } from "@/lib/api-base";

type ApiEnvelope<T> = {
  data: T;
  status: number;
  headers: Headers;
};

export type PricingMode = "fixed" | "hourly";
export type TaskType = "crawl" | "excel" | "report" | "code";
export type ArbitrationDecision = "refund" | "release_supplier";

export type SupplierRegisterPayload = {
  gateway_name: string;
  gateway_url: string;
  auth_token: string | null;
  allow_insecure_tls: boolean;
  disable_device_pairing: boolean;
  workspace_root: string;
  pricing: {
    mode: PricingMode;
    amount: number;
    currency: string;
  };
  availability: Array<{
    day: string;
    start: string;
    end: string;
  }>;
  max_concurrency: number;
  skill_tags: string[];
};

export type MarketplaceUpload = {
  filename: string;
  content_type: string;
  size_bytes: number;
  data_base64: string;
};

export type MarketplaceTaskCreatePayload = {
  description: string;
  budget_amount: number;
  deadline_at: string;
  task_type: TaskType;
  attachments: MarketplaceUpload[];
  public_market: boolean;
};

export type AgentSummary = {
  id: string;
  owner_id?: string | null;
  name: string;
  status: string;
  gateway_url?: string | null;
  skills: string[];
  pricing: Record<string, unknown>;
  availability: Array<Record<string, string>>;
  skill_tags: string[];
  max_concurrency: number;
  score: number;
  marketplace_enabled: boolean;
  gateway_id: string;
  is_board_lead: boolean;
  is_gateway_main: boolean;
  openclaw_session_id?: string | null;
  last_seen_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type SupplierAgentCard = {
  agent: AgentSummary;
  gateway_connected: boolean;
  imported_skills: string[];
  active_tasks: number;
  completed_tasks: number;
  total_revenue_amount: number;
};

export type MatchCandidate = {
  agent_id: string;
  owner_id?: string | null;
  name: string;
  score: number;
  current_load: number;
  max_concurrency: number;
  skills: string[];
  skill_tags: string[];
  pricing: Record<string, unknown>;
  reasons: string[];
};

export type TaskFileRef = {
  file_id: string;
  name: string;
  content_type: string;
  size_bytes: number;
  kind: string;
  storage_path: string;
  download_url: string;
  created_at: string;
};

export type PaymentSummary = {
  id: string;
  task_id: string;
  amount: number;
  currency: string;
  status: string;
  payer_id: string;
  payee_id: string;
  provider: string;
  provider_payment_id?: string | null;
  provider_client_secret?: string | null;
  platform_fee_amount: number;
  payee_amount: number;
  released_at?: string | null;
  refunded_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApprovalSummary = {
  id: string;
  action_type: string;
  status: string;
  created_at: string;
  resolved_at?: string | null;
};

export type TaskSummary = {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  priority: string;
  due_at?: string | null;
  assigned_agent_id?: string | null;
  created_by_user_id?: string | null;
  in_progress_at?: string | null;
  created_at: string;
  updated_at: string;
  blocked_by_task_ids: string[];
  is_blocked: boolean;
  tags: unknown[];
  custom_field_values?: Record<string, unknown> | null;
  marketplace_state?: string | null;
  marketplace_task_type?: string | null;
  marketplace_budget_amount?: number | null;
  marketplace_budget_currency?: string | null;
  marketplace_public: boolean;
  marketplace_listing_agent_id?: string | null;
  marketplace_attachments: TaskFileRef[];
  marketplace_match_candidates: MatchCandidate[];
  marketplace_delivery_artifacts: TaskFileRef[];
  marketplace_screenshots: TaskFileRef[];
  marketplace_delivery_note?: string | null;
  marketplace_failure_reason?: string | null;
};

export type MarketplaceTaskCard = {
  task: TaskSummary;
  payment?: PaymentSummary | null;
  listing_agent?: AgentSummary | null;
  worker_agent?: AgentSummary | null;
  pending_approvals: ApprovalSummary[];
};

export type SupplierDashboard = {
  agents: SupplierAgentCard[];
  active_tasks: MarketplaceTaskCard[];
  income_released_amount: number;
  income_pending_amount: number;
};

export type RequesterDashboard = {
  tasks: MarketplaceTaskCard[];
  history_cases: MarketplaceTaskCard[];
};

export type ArbitrationCase = {
  task: MarketplaceTaskCard;
  timeline: Array<{
    kind: string;
    event_type: string;
    message: string;
    created_at: string;
  }>;
};

const request = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const response = await customFetch<ApiEnvelope<T>>(url, init ?? { method: "GET" });
  return response.data;
};

const jsonRequest = async <T>(url: string, method: string, body?: unknown): Promise<T> =>
  request<T>(url, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

export const fileToUploadPayload = (file: File, dataBase64: string): MarketplaceUpload => ({
  filename: file.name,
  content_type: file.type || "application/octet-stream",
  size_bytes: file.size,
  data_base64: dataBase64,
});

export const fileToBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }
      reject(new Error("Unable to read file."));
    };
    reader.onerror = () => reject(new Error("Unable to read file."));
    reader.readAsDataURL(file);
  });

export const formatMoney = (amount?: number | null, currency = "CNY"): string => {
  const cents = Number.isFinite(amount ?? NaN) ? Number(amount) : 0;
  return `${currency.toUpperCase()} ${(cents / 100).toFixed(2)}`;
};

export const withApiBase = (path: string): string => `${getApiBaseUrl()}${path}`;

export const registerSupplierAgent = (payload: SupplierRegisterPayload) =>
  jsonRequest<SupplierAgentCard>("/api/v1/agents/register", "POST", payload);

export const importSupplierSkills = (agentId: string) =>
  jsonRequest<SupplierAgentCard>(`/api/v1/agents/${agentId}/skills/import`, "POST");

export const getMySupplierAgents = () =>
  request<SupplierAgentCard[]>("/api/v1/agents/me/marketplace");

export const getMarketplaceTasks = () =>
  request<MarketplaceTaskCard[]>("/api/v1/marketplace/tasks");

export const getRequesterTasks = () =>
  request<MarketplaceTaskCard[]>("/api/v1/marketplace/tasks/mine");

export const createMarketplaceTask = (payload: MarketplaceTaskCreatePayload) =>
  jsonRequest<MarketplaceTaskCard>("/api/v1/marketplace/tasks", "POST", payload);

export const rematchMarketplaceTask = (taskId: string) =>
  jsonRequest<MarketplaceTaskCard>("/api/v1/tasks/match", "POST", { task_id: taskId });

export const selectMarketplaceAgent = (taskId: string, agentId: string) =>
  jsonRequest<MarketplaceTaskCard>(`/api/v1/marketplace/tasks/${taskId}/select`, "POST", {
    agent_id: agentId,
  });

export const createEscrowPayment = (taskId: string, amount: number, currency = "cny") =>
  jsonRequest<PaymentSummary>("/api/v1/payments", "POST", {
    task_id: taskId,
    amount,
    currency,
  });

export const approveSupplierTask = (taskId: string, approve: boolean, comment?: string) =>
  jsonRequest<MarketplaceTaskCard>(
    `/api/v1/marketplace/tasks/${taskId}/supplier-approval`,
    "POST",
    { approve, comment },
  );

export const submitMarketplaceDelivery = (
  taskId: string,
  note: string,
  artifacts: MarketplaceUpload[],
) =>
  jsonRequest<MarketplaceTaskCard>(`/api/v1/marketplace/tasks/${taskId}/submit`, "POST", {
    note,
    artifacts,
  });

export const decideRequesterTask = (taskId: string, approve: boolean, comment?: string) =>
  jsonRequest<MarketplaceTaskCard>(
    `/api/v1/marketplace/tasks/${taskId}/requester-approval`,
    "POST",
    { approve, comment },
  );

export const failMarketplaceTask = (taskId: string, comment: string) =>
  jsonRequest<MarketplaceTaskCard>(`/api/v1/marketplace/tasks/${taskId}/fail`, "POST", {
    approve: false,
    comment,
  });

export const getSupplierDashboard = () =>
  request<SupplierDashboard>("/api/v1/supplier/dashboard");

export const getRequesterDashboard = () =>
  request<RequesterDashboard>("/api/v1/requester/dashboard");

export const getArbitrationCases = () =>
  request<ArbitrationCase[]>("/api/v1/admin/arbitration");

export const resolveArbitrationCase = (
  taskId: string,
  decision: ArbitrationDecision,
  comment?: string,
) =>
  jsonRequest<MarketplaceTaskCard>(`/api/v1/admin/arbitration/${taskId}`, "POST", {
    decision,
    comment,
  });
