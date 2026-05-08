export type ToolTrace = {
  tool_name: string | null;
  confidence: number;
  parameters: Record<string, unknown>;
  execution_time_ms: number;
  status: string;
  source: string | null;
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

export type AnalyticsSummary = {
  total_queries: number;
  average_latency_ms: number;
  fallback_count: number;
  fallback_rate: number;
  most_used_tool: string | null;
};

export type RecentQueryLog = {
  id: number;
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
