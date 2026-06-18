import { ContactResult, ContactSearchResponse } from "@/lib/api";

const MOCK_CONTACTS: ContactResult[] = [
  {
    id: "33333333-3333-4333-8333-333333333333",
    name: "Dr. Priya Nair",
    title: "Department Chair",
    department: "Computer Science",
    email: "pnair@example.edu",
    phone: "555-0142",
    office_location: "Science Hall 214",
    office_hours: "Tuesday and Thursday 2-4 PM",
    contact_type: "faculty",
    verification_status: "verified",
    status: "published",
    source_url: "https://www.caldwell.edu/academics/computer-science/",
    last_verified_at: "2026-05-28T12:00:00Z",
  },
  {
    id: "44444444-4444-4444-8444-444444444444",
    name: "Registrar Office",
    title: "Registrar",
    department: "Registrar",
    email: "registrar@example.edu",
    phone: "555-0100",
    office_location: "Admin 101",
    office_hours: "Monday-Friday 9 AM-5 PM",
    contact_type: "office",
    verification_status: "verified",
    status: "published",
    source_url: "https://www.caldwell.edu/registrar/",
    last_verified_at: "2026-05-28T12:00:00Z",
  },
  {
    id: "55555555-5555-4555-8555-555555555555",
    name: "Financial Aid Office",
    title: "Financial Aid",
    department: "Financial Aid",
    email: "finaid@example.edu",
    phone: "555-0188",
    office_location: "Student Services 120",
    office_hours: "Monday-Friday 8:30 AM-4:30 PM",
    contact_type: "office",
    verification_status: "verified",
    status: "published",
    source_url: "https://www.caldwell.edu/financial-aid/",
    last_verified_at: "2026-05-28T12:00:00Z",
  },
];

export function mockContactByIndex(index: number): ContactResult {
  return MOCK_CONTACTS[index];
}

export async function searchMockContacts(
  query: string,
  limit: number,
): Promise<ContactSearchResponse> {
  await wait(180);

  const normalizedQuery = query.trim().toLowerCase();
  const queryTerms = normalizedQuery.split(/[^a-z0-9@.]+/).filter(Boolean);
  const contacts = MOCK_CONTACTS.filter((contact) =>
    [
      contact.name,
      contact.title,
      contact.department,
      contact.email,
      contact.phone,
      contact.office_location,
      contact.contact_type,
    ].some((value) => {
      const normalizedValue = value?.toLowerCase();
      return (
        normalizedValue?.includes(normalizedQuery) ||
        queryTerms.some((term) => normalizedValue?.includes(term))
      );
    }),
  ).slice(0, limit);

  return {
    contacts,
    total: contacts.length,
    limit,
    offset: 0,
  };
}

export async function listMockContacts(
  limit: number,
  offset: number,
): Promise<ContactSearchResponse> {
  await wait(180);

  const contacts = MOCK_CONTACTS.slice(offset, offset + limit);
  return {
    contacts,
    total: MOCK_CONTACTS.length,
    limit,
    offset,
  };
}

export async function getMockContact(contactId: string): Promise<ContactResult> {
  await wait(120);

  const contact = MOCK_CONTACTS.find((mockContact) => mockContact.id === contactId);
  if (!contact) {
    throw new Error("CONTACT_NOT_FOUND");
  }
  return contact;
}

function wait(delayMs: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, delayMs);
  });
}
