import { QueryResponse } from "@/lib/api";

const MOCK_RESPONSES: Array<{
  keywords: string[];
  response: QueryResponse;
}> = [
  {
    keywords: ["add/drop", "add drop", "deadline"],
    response: {
      answer: "Mock response: The add/drop deadline for Spring 2026 is 2026-01-20.",
      tool_used: "deadline_query",
      confidence: 0.94,
      data: {
        results: [
          {
            type: "add_drop",
            term: "Spring 2026",
            date: "2026-01-20",
          },
        ],
        count: 1,
      },
      status: "success",
      trace: {
        tool_name: "deadline_query",
        confidence: 0.94,
        parameters: { type: "add_drop", term: "Spring 2026" },
        execution_time_ms: 12,
        status: "success",
        source: "mock",
        message: null,
      },
    },
  },
  {
    keywords: ["chair", "cs", "computer science"],
    response: {
      answer:
        "Mock response: Dr. Priya Nair is the Computer Science Department Chair.",
      tool_used: "contact_lookup",
      confidence: 0.87,
      data: {
        results: [
          {
            name: "Dr. Priya Nair",
            role: "Department Chair",
            department: "Computer Science",
          },
        ],
        count: 1,
      },
      status: "success",
      trace: {
        tool_name: "contact_lookup",
        confidence: 0.87,
        parameters: { department: "computer science", role: "chair" },
        execution_time_ms: 10,
        status: "success",
        source: "mock",
        message: null,
      },
    },
  },
  {
    keywords: ["register", "registration", "classes"],
    response: {
      answer:
        "Mock response: Log in to the student portal, open Registration, select your term, add courses, and submit your schedule.",
      tool_used: "reg_faq",
      confidence: 0.91,
      data: { results: [], count: 0 },
      status: "success",
      trace: {
        tool_name: "reg_faq",
        confidence: 0.91,
        parameters: { query: "register classes" },
        execution_time_ms: 9,
        status: "success",
        source: "mock",
        message: null,
      },
    },
  },
];

export async function sendMockQuery(query: string): Promise<QueryResponse> {
  const normalizedQuery = query.trim().toLowerCase();
  const match = MOCK_RESPONSES.find((mockResponse) =>
    mockResponse.keywords.some((keyword) => normalizedQuery.includes(keyword)),
  );

  await new Promise((resolve) => {
    window.setTimeout(resolve, 250);
  });

  return (
    match?.response ?? {
      answer:
        "Mock response: I am not confident about that request. Try deadlines, contacts, events, calendar dates, or registration help.",
      tool_used: null,
      confidence: 0.2,
      data: {},
      status: "fallback",
      trace: {
        tool_name: null,
        confidence: 0.2,
        parameters: {},
        execution_time_ms: 0,
        status: "fallback",
        source: null,
        message: "Mock fallback: no matching tool selected.",
      },
    }
  );
}
