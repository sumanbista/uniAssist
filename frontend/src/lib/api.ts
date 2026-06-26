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

export type ContactResult = {
  id: string;
  name: string;
  title: string | null;
  department: string | null;
  email: string | null;
  phone: string | null;
  office_location: string | null;
  office_hours: string | null;
  contact_type: string;
  verification_status: string;
  status: string;
  source_url: string | null;
  last_verified_at: string | null;
};

export type ContactSearchResponse = {
  contacts: ContactResult[];
  total: number;
  limit: number;
  offset: number;
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

export type PdfFormUploadInput = {
  file: File;
  title: string;
  description?: string;
  category?: string;
  department?: string;
  source_url?: string;
};

export type PdfFormUploadResponse = {
  form_id: string;
  title: string;
  status: string;
  verification_status: string;
  extracted_text_preview: string;
  page_count: number;
};

export type ReviewItem = {
  entity_type: "form";
  entity_id: string;
  title: string;
  category: string | null;
  source_url: string | null;
  status: string;
  verification_status: string;
  submitted_at: string;
  source_metadata: Record<string, unknown>;
  file_url: string;
};

export type ReviewDecision = "approve" | "reject";

export type ReviewDecisionInput = {
  entity_type: "form";
  entity_id: string;
  decision: ReviewDecision;
  review_notes?: string;
};

export type ReviewDecisionResponse = {
  entity_type: "form";
  entity_id: string;
  decision: ReviewDecision;
  status: string;
  verification_status: string;
  review_notes: string | null;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const USE_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";
const JWT_STORAGE_KEY = "uniassist_jwt";

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
      ...authHeaders(),
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
    headers: authHeaders(),
  });

  if (response.status === 401 || response.status === 403) {
    throw new Error("FORM_SEARCH_UNAUTHORIZED");
  }
  if (!response.ok) {
    throw new Error("FORM_SEARCH_UNAVAILABLE");
  }

  return validateFormSearchResponse(await response.json());
}

export async function searchContacts(
  query: string,
  limit = 5,
): Promise<ContactSearchResponse> {
  if (USE_MOCK_API) {
    const { searchMockContacts } = await import("@/lib/mockContacts");
    return searchMockContacts(query, limit);
  }

  const searchParams = new URLSearchParams({
    q: query,
    limit: String(limit),
  });
  const response = await fetch(`${API_BASE_URL}/contacts/search?${searchParams}`, {
    headers: authHeaders(),
  });

  if (response.status === 401 || response.status === 403) {
    throw new Error("CONTACT_SEARCH_UNAUTHORIZED");
  }
  if (!response.ok) {
    throw new Error("CONTACT_SEARCH_UNAVAILABLE");
  }

  return validateContactSearchResponse(await response.json());
}

export async function getContacts(limit = 20, offset = 0): Promise<ContactSearchResponse> {
  if (USE_MOCK_API) {
    const { listMockContacts } = await import("@/lib/mockContacts");
    return listMockContacts(limit, offset);
  }

  const searchParams = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const response = await fetch(`${API_BASE_URL}/contacts?${searchParams}`, {
    headers: authHeaders(),
  });

  if (response.status === 401 || response.status === 403) {
    throw new Error("CONTACTS_UNAUTHORIZED");
  }
  if (!response.ok) {
    throw new Error("CONTACTS_UNAVAILABLE");
  }

  return validateContactSearchResponse(await response.json());
}

export async function getContact(contactId: string): Promise<ContactResult> {
  if (!isUuidLike(contactId)) {
    throw new Error("CONTACT_INVALID_ID");
  }

  if (USE_MOCK_API) {
    const { getMockContact } = await import("@/lib/mockContacts");
    return getMockContact(contactId);
  }

  const response = await fetch(
    `${API_BASE_URL}/contacts/${encodeURIComponent(contactId)}`,
    { headers: authHeaders() },
  );

  if (response.status === 401 || response.status === 403) {
    throw new Error("CONTACT_UNAUTHORIZED");
  }
  if (response.status === 404) {
    throw new Error("CONTACT_NOT_FOUND");
  }
  if (!response.ok) {
    throw new Error("CONTACT_UNAVAILABLE");
  }

  return validateContactResult(await response.json());
}

export async function uploadPdfForm(
  input: PdfFormUploadInput,
): Promise<PdfFormUploadResponse> {
  const formData = new FormData();
  formData.append("file", input.file);
  appendFormValue(formData, "title", input.title);
  appendFormValue(formData, "description", input.description);
  appendFormValue(formData, "category", input.category);
  appendFormValue(formData, "department", input.department);
  appendFormValue(formData, "source_url", input.source_url);

  const response = await fetch(`${API_BASE_URL}/ingestion/forms/pdf`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (response.status === 401 || response.status === 403) {
    throw new Error("ADMIN_UNAUTHORIZED");
  }
  if (!response.ok) {
    throw new Error("UPLOAD_FAILED");
  }

  return validatePdfFormUploadResponse(await response.json());
}

export async function getPendingReviews(): Promise<ReviewItem[]> {
  const response = await fetch(
    `${API_BASE_URL}/governance/reviews/pending?entity_type=form`,
    { headers: authHeaders() },
  );

  if (response.status === 401 || response.status === 403) {
    throw new Error("ADMIN_UNAUTHORIZED");
  }
  if (!response.ok) {
    throw new Error("REVIEWS_UNAVAILABLE");
  }

  return validateReviewItems(await response.json());
}

export async function getReviewItem(
  entityType: string,
  entityId: string,
): Promise<ReviewItem> {
  const response = await fetch(
    `${API_BASE_URL}/governance/reviews/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}`,
    { headers: authHeaders() },
  );

  if (response.status === 401 || response.status === 403) {
    throw new Error("ADMIN_UNAUTHORIZED");
  }
  if (response.status === 404) {
    throw new Error("REVIEW_NOT_FOUND");
  }
  if (!response.ok) {
    throw new Error("REVIEWS_UNAVAILABLE");
  }

  return validateReviewItem(await response.json());
}

export async function submitReviewDecision(
  input: ReviewDecisionInput,
): Promise<ReviewDecisionResponse> {
  const response = await fetch(`${API_BASE_URL}/governance/reviews/decision`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify({
      entity_type: input.entity_type,
      entity_id: input.entity_id,
      decision: input.decision,
      review_notes: input.review_notes,
    }),
  });

  if (response.status === 401 || response.status === 403) {
    throw new Error("ADMIN_UNAUTHORIZED");
  }
  if (response.status === 409) {
    throw new Error("REVIEW_CONFLICT");
  }
  if (!response.ok) {
    throw new Error("REVIEW_DECISION_FAILED");
  }

  return validateReviewDecisionResponse(await response.json());
}

export function getFormFileUrl(formId: string): string {
  const encodedFormId = encodeURIComponent(formId);
  return `${API_BASE_URL}/forms/${encodedFormId}/file`;
}

export async function openFormPdf(formId: string): Promise<void> {
  const response = await fetch(getFormFileUrl(formId), {
    headers: authHeaders(),
  });
  if (response.status === 401 || response.status === 403) {
    throw new Error("FORM_FILE_UNAUTHORIZED");
  }
  if (!response.ok) {
    throw new Error("FORM_FILE_UNAVAILABLE");
  }
  const pdfBlob = await response.blob();
  const pdfUrl = URL.createObjectURL(pdfBlob);
  window.open(pdfUrl, "_blank", "noopener,noreferrer");
  window.setTimeout(() => URL.revokeObjectURL(pdfUrl), 60_000);
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

export function extractContactResults(value: unknown): ContactResult[] {
  const containers = collectContactContainers(value);
  const contacts = containers.flatMap((container) => {
    if (Array.isArray(container)) {
      return container;
    }
    if (isRecord(container) && Array.isArray(container.contacts)) {
      return container.contacts;
    }
    if (isRecord(container) && Array.isArray(container.results)) {
      return container.results;
    }
    return [];
  });

  return contacts.map(normalizeContactResult).filter((contact) => contact !== null);
}

async function fetchAnalytics<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error("Analytics are available to admins only.");
  }
  return response.json() as Promise<T>;
}

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  return fetchAnalytics<AnalyticsSummary>("/analytics/summary");
}

export async function fetchAnalyticsTools(): Promise<Record<string, number>> {
  return fetchAnalytics<Record<string, number>>("/analytics/tools");
}

export async function fetchAnalyticsRoles(): Promise<Record<string, number>> {
  return fetchAnalytics<Record<string, number>>("/analytics/roles");
}

export async function fetchRecentQueries(): Promise<RecentQueryLog[]> {
  return fetchAnalytics<RecentQueryLog[]>("/analytics/recent");
}

function authHeaders(): Record<string, string> {
  const token = authToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getStoredAuthToken(): string {
  if (typeof window === "undefined") {
    return "";
  }
  return window.localStorage.getItem(JWT_STORAGE_KEY)?.trim() || "";
}

export function saveStoredAuthToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  const normalizedToken = token.trim();
  if (normalizedToken) {
    window.localStorage.setItem(JWT_STORAGE_KEY, normalizedToken);
  } else {
    window.localStorage.removeItem(JWT_STORAGE_KEY);
  }
}

export function clearStoredAuthToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(JWT_STORAGE_KEY);
}

function authToken(): string | null {
  const envToken = process.env.NEXT_PUBLIC_DEMO_JWT?.trim();
  if (envToken) {
    return envToken;
  }
  if (typeof window === "undefined") {
    return null;
  }
  const storedToken = getStoredAuthToken();
  if (!storedToken) {
    return null;
  }
  if (isExpiredJwt(storedToken)) {
    clearStoredAuthToken();
    return null;
  }
  return storedToken;
}

function isExpiredJwt(token: string): boolean {
  const [, payload] = token.split(".");
  if (!payload) {
    return false;
  }
  try {
    const normalizedPayload = payload.replace(/-/g, "+").replace(/_/g, "/");
    const paddedPayload = normalizedPayload.padEnd(
      normalizedPayload.length + ((4 - (normalizedPayload.length % 4)) % 4),
      "=",
    );
    const decodedPayload = JSON.parse(
      window.atob(paddedPayload),
    ) as unknown;
    if (!isRecord(decodedPayload) || typeof decodedPayload.exp !== "number") {
      return false;
    }
    return decodedPayload.exp <= Math.floor(Date.now() / 1000);
  } catch {
    return false;
  }
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

function validateContactSearchResponse(value: unknown): ContactSearchResponse {
  if (!isRecord(value) || !Array.isArray(value.contacts)) {
    throw new Error("CONTACT_SEARCH_INVALID_RESPONSE");
  }
  return {
    contacts: value.contacts.map((contact) =>
      validateContactListItem(contact, "CONTACT_SEARCH_INVALID_RESPONSE"),
    ),
    total: typeof value.total === "number" ? value.total : 0,
    limit: typeof value.limit === "number" ? value.limit : 0,
    offset: typeof value.offset === "number" ? value.offset : 0,
  };
}

function validateContactResult(value: unknown): ContactResult {
  const contact = normalizeContactResult(value);
  if (!contact) {
    throw new Error("CONTACT_INVALID_RESPONSE");
  }
  return contact;
}

function validateContactListItem(
  value: unknown,
  errorMessage: string,
): ContactResult {
  const contact = normalizeContactResult(value);
  if (!contact) {
    throw new Error(errorMessage);
  }
  return contact;
}

function validatePdfFormUploadResponse(value: unknown): PdfFormUploadResponse {
  if (!isRecord(value)) {
    throw new Error("UPLOAD_INVALID_RESPONSE");
  }
  const formId = safeString(value.form_id);
  const title = safeString(value.title);
  const status = safeString(value.status);
  const verificationStatus = safeString(value.verification_status);
  if (!formId || !isUuidLike(formId) || !title || !status || !verificationStatus) {
    throw new Error("UPLOAD_INVALID_RESPONSE");
  }
  return {
    form_id: formId,
    title,
    status,
    verification_status: verificationStatus,
    extracted_text_preview: safeString(value.extracted_text_preview) ?? "",
    page_count: typeof value.page_count === "number" ? value.page_count : 0,
  };
}

function validateReviewItems(value: unknown): ReviewItem[] {
  if (!Array.isArray(value)) {
    throw new Error("REVIEWS_INVALID_RESPONSE");
  }
  return value.map(validateReviewItem);
}

function validateReviewItem(value: unknown): ReviewItem {
  if (!isRecord(value)) {
    throw new Error("REVIEWS_INVALID_RESPONSE");
  }
  const entityType = safeString(value.entity_type);
  const entityId = safeString(value.entity_id);
  const title = safeString(value.title);
  const status = safeString(value.status);
  const verificationStatus = safeString(value.verification_status);
  const submittedAt = safeString(value.submitted_at);
  if (
    entityType !== "form" ||
    !entityId ||
    !isUuidLike(entityId) ||
    !title ||
    !status ||
    !verificationStatus ||
    !submittedAt
  ) {
    throw new Error("REVIEWS_INVALID_RESPONSE");
  }
  return {
    entity_type: "form",
    entity_id: entityId,
    title,
    category: safeNullableString(value.category),
    source_url: safeHttpUrl(value.source_url),
    status,
    verification_status: verificationStatus,
    submitted_at: submittedAt,
    source_metadata: isRecord(value.source_metadata) ? value.source_metadata : {},
    file_url: getFormFileUrl(entityId),
  };
}

function validateReviewDecisionResponse(
  value: unknown,
): ReviewDecisionResponse {
  if (!isRecord(value)) {
    throw new Error("REVIEW_DECISION_INVALID_RESPONSE");
  }
  const entityType = safeString(value.entity_type);
  const entityId = safeString(value.entity_id);
  const decision = safeString(value.decision);
  const status = safeString(value.status);
  const verificationStatus = safeString(value.verification_status);
  if (
    entityType !== "form" ||
    !entityId ||
    !isUuidLike(entityId) ||
    (decision !== "approve" && decision !== "reject") ||
    !status ||
    !verificationStatus
  ) {
    throw new Error("REVIEW_DECISION_INVALID_RESPONSE");
  }
  return {
    entity_type: "form",
    entity_id: entityId,
    decision,
    status,
    verification_status: verificationStatus,
    review_notes: safeNullableString(value.review_notes),
  };
}

function appendFormValue(formData: FormData, key: string, value?: string) {
  const normalizedValue = value?.trim();
  if (normalizedValue) {
    formData.append(key, normalizedValue);
  }
}

function normalizeFormResult(value: unknown): FormResult | null {
  if (!isRecord(value)) {
    return null;
  }
  if (isContactLikeRecord(value)) {
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

function normalizeContactResult(value: unknown): ContactResult | null {
  if (!isRecord(value)) {
    return null;
  }
  const id = safeString(value.id);
  const name = safeString(value.name);
  const contactType = safeString(value.contact_type);
  if (!id || !isUuidLike(id) || !name || !contactType) {
    return null;
  }

  return {
    id,
    name,
    title: safeNullableString(value.title),
    department: safeNullableString(value.department),
    email: safeEmail(value.email),
    phone: safeNullableString(value.phone),
    office_location: safeNullableString(value.office_location),
    office_hours: safeNullableString(value.office_hours),
    contact_type: contactType,
    verification_status: safeString(value.verification_status) ?? "unknown",
    status: safeString(value.status) ?? "unknown",
    source_url: safeHttpUrl(value.source_url),
    last_verified_at: safeNullableString(value.last_verified_at),
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

function collectContactContainers(value: unknown): unknown[] {
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
  if (isRecord(value.results) && !Array.isArray(value.results)) {
    containers.push(value.results);
    const contactLookup = value.results.contact_lookup;
    if (Array.isArray(contactLookup)) {
      containers.push(contactLookup);
    }
  }
  return containers;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isContactLikeRecord(value: Record<string, unknown>): boolean {
  return (
    typeof value.contact_type === "string" ||
    typeof value.email === "string" ||
    typeof value.office_location === "string" ||
    typeof value.office_hours === "string"
  );
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

function safeEmail(value: unknown): string | null {
  const candidate = safeString(value);
  if (!candidate || candidate.length > 254 || /[\s<>]/.test(candidate)) {
    return null;
  }
  return /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(candidate)
    ? candidate
    : null;
}

function isUuidLike(value: unknown): boolean {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  );
}
