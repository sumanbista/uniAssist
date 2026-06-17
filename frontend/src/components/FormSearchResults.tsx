"use client";

import { useState } from "react";

import { FormResult, openFormPdf } from "@/lib/api";

export type FormResultsState =
  | { status: "idle"; forms: [] }
  | { status: "loading"; forms: [] }
  | { status: "success"; forms: FormResult[] }
  | { status: "empty"; forms: [] }
  | { status: "unauthorized"; forms: [] }
  | { status: "error"; forms: [] };

type FormSearchResultsProps = {
  state: FormResultsState;
};

export function FormSearchResults({ state }: FormSearchResultsProps) {
  const [openErrorId, setOpenErrorId] = useState("");

  if (state.status === "idle") {
    return null;
  }

  if (state.status === "loading") {
    return (
      <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-3 text-sm text-zinc-600">
        Searching verified forms...
      </div>
    );
  }

  if (state.status === "empty") {
    return (
      <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-3 text-sm text-zinc-600">
        No verified forms matched this search.
      </div>
    );
  }

  if (state.status === "unauthorized") {
    return (
      <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-900">
        Form search is not available for this session.
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-3 text-sm text-red-900">
        Forms could not be loaded. Check that the backend is running and available.
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-2">
      {state.forms.map((form) => (
        <article
          className="rounded-lg border border-zinc-200 bg-zinc-50 p-3"
          key={form.form_id}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-zinc-950">{form.title}</h2>
              {form.description ? (
                <p className="mt-1 text-sm leading-5 text-zinc-600">
                  {form.description}
                </p>
              ) : null}
              <dl className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-600">
                {form.category ? (
                  <MetaPill label="Category" value={form.category} />
                ) : null}
                <MetaPill label="Status" value={formatStatus(form.verification_status)} />
                {form.last_verified_at ? (
                  <MetaPill
                    label="Verified"
                    value={formatDate(form.last_verified_at)}
                  />
                ) : null}
                {typeof form.ranking_score === "number" ? (
                  <MetaPill
                    label="Match"
                    value={`${Math.round(form.ranking_score * 100)}%`}
                  />
                ) : null}
              </dl>
              {form.source_url ? (
                <a
                  className="mt-2 inline-block break-all text-xs font-medium text-teal-700 hover:text-teal-800"
                  href={form.source_url}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  Source
                </a>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-col gap-2">
              <button
              className="inline-flex h-9 shrink-0 items-center justify-center rounded-lg bg-teal-700 px-3 text-sm font-semibold text-white transition hover:bg-teal-800"
                onClick={() =>
                  void openFormPdf(form.form_id)
                    .then(() => setOpenErrorId(""))
                    .catch(() => setOpenErrorId(form.form_id))
                }
                type="button"
              >
                Open Form
              </button>
              {openErrorId === form.form_id ? (
                <p className="text-xs text-red-700">PDF unavailable for this session.</p>
              ) : null}
            </div>
          </div>
        </article>
      ))}
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
