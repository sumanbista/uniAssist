export type ToolTrace = {
  tool_name: string | null;
  confidence: number;
  parameters: Record<string, unknown>;
  execution_time_ms: number;
  status: string;
  source: string | null;
  last_updated?: string | null;
  request_id?: string | null;
  message: string | null;
  role: UserRole | string | null;
  authorized: boolean;
  error_type: string | null;
};

export type UserRole = "student" | "faculty" | "admin";

export type QueryResponse = {
  answer: string;
  tool_used: string | null;
  confidence: number;
  data: unknown;
  status: "success" | "fallback" | string;
  trace: ToolTrace;
};

export type QueryData = {
  results?: unknown[];
  count?: number;
};

export type FormResult = {
  form_id: string;
  title: string;
  description: string | null;
  category: string | null;
  verification_status: string;
  status: string;
  ranking_score: number | null;
  source_url: string | null;
  last_verified_at: string | null;
  file_url: string;
};

export type FormSearchResponse = {
  forms: FormResult[];
  query: string;
  limit: number;
};

export type AnalyticsSummary = {
  total_queries: number;
  average_latency_ms: number;
  fallback_count: number;
  fallback_rate: number;
  most_used_tool: string | null;
};

export type RecentQueryLog = {
  id: number;
  request_id: string;
  query: string;
  tool_used: string | null;
  role: string | null;
  confidence: number;
  latency_ms: number;
  fallback_triggered: boolean;
  status: string;
  created_at: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";
const UNIVERSITY_ID =
  process.env.NEXT_PUBLIC_UNIVERSITY_ID ??
  "11111111-1111-4111-8111-111111111111";

export async function sendQuery(
  query: string,
  role: UserRole,
): Promise<QueryResponse> {
  if (USE_MOCK_API) {
    const { sendMockQuery } = await import("@/lib/mockApi");
    return sendMockQuery(query, role);
  }

  const response = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message: query, role }),
  });

  if (!response.ok) {
    throw new Error("The UniAssist API returned an error.");
  }

  return response.json() as Promise<QueryResponse>;
}

export async function searchForms(
  query: string,
  limit = 5,
): Promise<FormSearchResponse> {
  if (USE_MOCK_API) {
    const { searchMockForms } = await import("@/lib/mockApi");
    return searchMockForms(query, limit);
  }

  const searchParams = new URLSearchParams({
    q: query,
    limit: String(limit),
  });
  const response = await fetch(`${API_BASE_URL}/forms/search?${searchParams}`, {
    headers: {
      "X-University-ID": UNIVERSITY_ID,
    },
  });

  if (response.status === 401 || response.status === 403) {
    throw new Error("FORM_SEARCH_UNAUTHORIZED");
  }
  if (!response.ok) {
    throw new Error("FORM_SEARCH_UNAVAILABLE");
  }

  return validateFormSearchResponse(await response.json());
}

export function getFormFileUrl(formId: string): string {
  const encodedFormId = encodeURIComponent(formId);
  return `${API_BASE_URL}/forms/${encodedFormId}/file`;
}

export function extractFormResults(value: unknown): FormResult[] {
  const containers = collectFormContainers(value);
  const forms = containers.flatMap((container) => {
    if (Array.isArray(container)) {
      return container;
    }
    if (isRecord(container) && Array.isArray(container.forms)) {
      return container.forms;
    }
    if (isRecord(container) && Array.isArray(container.results)) {
      return container.results;
    }
    return [];
  });

  return forms.map(normalizeFormResult).filter((form) => form !== null);
}

async function fetchAnalytics<T>(path: string, role: UserRole): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}?role=${role}`);
  if (!response.ok) {
    throw new Error("Analytics are available to admins only.");
  }
  return response.json() as Promise<T>;
}

export async function fetchAnalyticsSummary(role: UserRole): Promise<AnalyticsSummary> {
  return fetchAnalytics<AnalyticsSummary>("/analytics/summary", role);
}

export async function fetchAnalyticsTools(role: UserRole): Promise<Record<string, number>> {
  return fetchAnalytics<Record<string, number>>("/analytics/tools", role);
}

export async function fetchAnalyticsRoles(role: UserRole): Promise<Record<string, number>> {
  return fetchAnalytics<Record<string, number>>("/analytics/roles", role);
}

export async function fetchRecentQueries(role: UserRole): Promise<RecentQueryLog[]> {
  return fetchAnalytics<RecentQueryLog[]>("/analytics/recent", role);
}

function validateFormSearchResponse(value: unknown): FormSearchResponse {
  if (!isRecord(value) || !Array.isArray(value.forms)) {
    throw new Error("FORM_SEARCH_INVALID_RESPONSE");
  }

  return {
    forms: value.forms
      .map(normalizeFormResult)
      .filter((form) => form !== null),
    query: typeof value.query === "string" ? value.query : "",
    limit: typeof value.limit === "number" ? value.limit : 0,
  };
}

function normalizeFormResult(value: unknown): FormResult | null {
  if (!isRecord(value)) {
    return null;
  }
  const rawId = value.form_id ?? value.id;
  const title = safeString(value.title);
  if (!isUuidLike(rawId) || !title) {
    return null;
  }

  return {
    form_id: String(rawId),
    title,
    description: safeNullableString(value.description),
    category: safeNullableString(value.category),
    verification_status: safeString(value.verification_status) ?? "unknown",
    status: safeString(value.status) ?? "unknown",
    ranking_score:
      typeof value.ranking_score === "number" && Number.isFinite(value.ranking_score)
        ? value.ranking_score
        : null,
    source_url: safeHttpUrl(value.source_url),
    last_verified_at: safeNullableString(value.last_verified_at),
    file_url: getFormFileUrl(String(rawId)),
  };
}

function collectFormContainers(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return [value];
  }
  if (!isRecord(value)) {
    return [];
  }

  const containers: unknown[] = [value];
  if (isRecord(value.data)) {
    containers.push(value.data);
  }
  if (isRecord(value.results)) {
    Object.values(value.results).forEach((result) => containers.push(result));
  }
  return containers;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.replace(/\u0000/g, "").trim();
  return normalized || null;
}

function safeNullableString(value: unknown): string | null {
  return safeString(value);
}

function safeHttpUrl(value: unknown): string | null {
  const candidate = safeString(value);
  if (!candidate) {
    return null;
  }
  try {
    const parsed = new URL(candidate);
    return parsed.protocol === "http:" || parsed.protocol === "https:"
      ? parsed.toString()
      : null;
  } catch {
    return null;
  }
}

function isUuidLike(value: unknown): boolean {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  );
}
