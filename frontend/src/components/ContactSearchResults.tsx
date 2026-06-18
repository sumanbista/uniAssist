"use client";

import { ReactNode } from "react";

import { ContactResult } from "@/lib/api";

export type ContactResultsState =
  | { status: "idle"; contacts: [] }
  | { status: "loading"; contacts: [] }
  | { status: "success"; contacts: ContactResult[] }
  | { status: "empty"; contacts: [] }
  | { status: "unauthorized"; contacts: [] }
  | { status: "error"; contacts: [] };

type ContactSearchResultsProps = {
  state: ContactResultsState;
};

export function ContactSearchResults({ state }: ContactSearchResultsProps) {
  if (state.status === "idle") {
    return null;
  }

  if (state.status === "loading") {
    return (
      <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-3 text-sm text-zinc-600">
        Searching verified contacts...
      </div>
    );
  }

  if (state.status === "empty") {
    return (
      <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-3 text-sm text-zinc-600">
        No verified contacts matched this search.
      </div>
    );
  }

  if (state.status === "unauthorized") {
    return (
      <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-900">
        Contact search is not available for this session.
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-900">
        Contacts could not be loaded. Check that the backend is running and available.
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-2">
      {state.contacts.map((contact) => (
        <article
          className="rounded-lg border border-zinc-200 bg-zinc-50 p-3"
          key={contact.id}
        >
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-zinc-950">{contact.name}</h2>
            {contact.title || contact.department ? (
              <p className="mt-1 text-sm text-zinc-700">
                {[contact.title, contact.department].filter(Boolean).join(" · ")}
              </p>
            ) : null}
            <dl className="mt-2 grid gap-2 text-sm text-zinc-600">
              {contact.email ? (
                <ContactDetail label="Email">
                  <a
                    className="break-all font-medium text-teal-700 hover:text-teal-800"
                    href={`mailto:${contact.email}`}
                  >
                    {contact.email}
                  </a>
                </ContactDetail>
              ) : null}
              {contact.phone ? (
                <ContactDetail label="Phone">{contact.phone}</ContactDetail>
              ) : null}
              {contact.office_location ? (
                <ContactDetail label="Office">{contact.office_location}</ContactDetail>
              ) : null}
              {contact.office_hours ? (
                <ContactDetail label="Hours">{contact.office_hours}</ContactDetail>
              ) : null}
            </dl>
            <dl className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-600">
              <MetaPill label="Type" value={formatStatus(contact.contact_type)} />
              <MetaPill
                label="Verification"
                value={formatStatus(contact.verification_status)}
              />
              <MetaPill label="Status" value={formatStatus(contact.status)} />
              {contact.last_verified_at ? (
                <MetaPill
                  label="Verified"
                  value={formatDate(contact.last_verified_at)}
                />
              ) : null}
            </dl>
            {contact.source_url ? (
              <a
                className="mt-2 inline-block break-all text-xs font-medium text-teal-700 hover:text-teal-800"
                href={contact.source_url}
                rel="noopener noreferrer"
                target="_blank"
              >
                Source
              </a>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function ContactDetail({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
      <dt className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
        {label}
      </dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

function MetaPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-white px-2 py-1 ring-1 ring-zinc-200">
      <dt className="sr-only">{label}</dt>
      <dd>
        <span className="font-medium">{label}:</span> {value}
      </dd>
    </div>
  );
}

function formatStatus(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}
