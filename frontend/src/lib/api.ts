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
