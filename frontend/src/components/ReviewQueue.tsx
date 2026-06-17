"use client";

import { useEffect, useState } from "react";

import {
  getPendingReviews,
  getReviewItem,
  openFormPdf,
  ReviewDecision,
  ReviewItem,
  submitReviewDecision,
} from "@/lib/api";

type ReviewQueueProps = {
  refreshKey: number;
};

type QueueState =
  | { status: "loading"; reviews: ReviewItem[] }
  | { status: "success"; reviews: ReviewItem[] }
  | { status: "empty"; reviews: [] }
  | { status: "unauthorized"; reviews: [] }
  | { status: "error"; reviews: [] };

export function ReviewQueue({ refreshKey }: ReviewQueueProps) {
  const [queueState, setQueueState] = useState<QueueState>({
    status: "loading",
    reviews: [],
  });
  const [notesById, setNotesById] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadReviews() {
      setQueueState({ status: "loading", reviews: [] });
      setMessage("");
      try {
        const reviews = await getPendingReviews();
        if (isMounted) {
          setQueueState(
            reviews.length
              ? { status: "success", reviews }
              : { status: "empty", reviews: [] },
          );
        }
      } catch (error) {
        if (isMounted) {
          setQueueState({
            status:
              error instanceof Error && error.message === "ADMIN_UNAUTHORIZED"
                ? "unauthorized"
                : "error",
            reviews: [],
          });
        }
      }
    }

    void loadReviews();

    return () => {
      isMounted = false;
    };
  }, [refreshKey]);

  async function decide(review: ReviewItem, decision: ReviewDecision) {
    setBusyId(review.entity_id);
    setMessage("");
    try {
      await getReviewItem(review.entity_type, review.entity_id);
      const response = await submitReviewDecision({
        entity_type: review.entity_type,
        entity_id: review.entity_id,
        decision,
        review_notes: notesById[review.entity_id],
      });
      setMessage(`${review.title} ${response.status}.`);
      setQueueState((current) => {
        const reviews = current.reviews.filter(
          (item) => item.entity_id !== review.entity_id,
        );
        return reviews.length
          ? { status: "success", reviews }
          : { status: "empty", reviews: [] };
      });
    } catch (error) {
      setMessage(reviewErrorMessage(error));
    } finally {
      setBusyId("");
    }
  }

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-950">Pending review queue</h2>
          <p className="mt-1 text-sm text-zinc-500">
            Review uploaded forms before they become verified resources.
          </p>
        </div>
        <button
          className="h-9 rounded-lg border border-zinc-300 px-3 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50 disabled:cursor-not-allowed disabled:text-zinc-400"
          disabled={queueState.status === "loading"}
          onClick={() => {
            setQueueState({ status: "loading", reviews: [] });
            void getPendingReviews()
              .then((reviews) =>
                setQueueState(
                  reviews.length
                    ? { status: "success", reviews }
                    : { status: "empty", reviews: [] },
                ),
              )
              .catch((error) =>
                setQueueState({
                  status:
                    error instanceof Error &&
                    error.message === "ADMIN_UNAUTHORIZED"
                      ? "unauthorized"
                      : "error",
                  reviews: [],
                }),
              );
          }}
          type="button"
        >
          Refresh
        </button>
      </div>

      {message ? (
        <div className="mt-4 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-700">
          {message}
        </div>
      ) : null}

      <QueueBody
        busyId={busyId}
        notesById={notesById}
        onDecide={decide}
        onOpenError={() => setMessage("The PDF could not be opened for this session.")}
        onNotesChange={(entityId, value) =>
          setNotesById((current) => ({ ...current, [entityId]: value }))
        }
        state={queueState}
      />
    </section>
  );
}

function QueueBody({
  busyId,
  notesById,
  onDecide,
  onOpenError,
  onNotesChange,
  state,
}: {
  busyId: string;
  notesById: Record<string, string>;
  onDecide: (review: ReviewItem, decision: ReviewDecision) => void;
  onOpenError: () => void;
  onNotesChange: (entityId: string, value: string) => void;
  state: QueueState;
}) {
  if (state.status === "loading") {
    return <StatusPanel message="Loading pending reviews..." />;
  }
  if (state.status === "unauthorized") {
    return <StatusPanel message="Admin authorization is required for review actions." />;
  }
  if (state.status === "error") {
    return <StatusPanel message="The review queue could not be loaded." />;
  }
  if (state.status === "empty") {
    return <StatusPanel message="No forms are waiting for review." />;
  }

  return (
    <div className="mt-5 space-y-3">
      {state.reviews.map((review) => (
        <article
          className="rounded-lg border border-zinc-200 bg-zinc-50 p-4"
          key={review.entity_id}
        >
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <h3 className="text-base font-semibold text-zinc-950">{review.title}</h3>
              <dl className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-600">
                {review.category ? (
                  <Meta label="Category" value={review.category} />
                ) : null}
                <Meta label="Status" value={formatStatus(review.status)} />
                <Meta
                  label="Verification"
                  value={formatStatus(review.verification_status)}
                />
                <Meta label="Submitted" value={formatDate(review.submitted_at)} />
              </dl>
              {review.source_url ? (
                <a
                  className="mt-2 inline-block break-all text-xs font-medium text-teal-700 hover:text-teal-800"
                  href={review.source_url}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  Source
                </a>
              ) : null}
            </div>
            <button
              className="inline-flex h-9 shrink-0 items-center justify-center rounded-lg border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-800 transition hover:bg-zinc-100"
              onClick={() =>
                void openFormPdf(review.entity_id).catch(onOpenError)
              }
              type="button"
            >
              Open PDF
            </button>
          </div>
          <label
            className="mt-4 block text-sm font-medium text-zinc-700"
            htmlFor={`notes-${review.entity_id}`}
          >
            Review notes
          </label>
          <textarea
            className="mt-2 block min-h-20 w-full resize-y rounded-lg border border-zinc-300 px-3 py-2 text-sm text-zinc-950 outline-none transition focus:border-teal-500 focus:ring-2 focus:ring-teal-100 disabled:bg-zinc-100"
            disabled={busyId === review.entity_id}
            id={`notes-${review.entity_id}`}
            onChange={(event) => onNotesChange(review.entity_id, event.target.value)}
            value={notesById[review.entity_id] ?? ""}
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              className="h-9 rounded-lg bg-teal-700 px-3 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
              disabled={busyId === review.entity_id}
              onClick={() => onDecide(review, "approve")}
              type="button"
            >
              {busyId === review.entity_id ? "Working..." : "Approve"}
            </button>
            <button
              className="h-9 rounded-lg border border-red-300 bg-white px-3 text-sm font-semibold text-red-700 transition hover:bg-red-50 disabled:cursor-not-allowed disabled:text-zinc-400"
              disabled={busyId === review.entity_id}
              onClick={() => onDecide(review, "reject")}
              type="button"
            >
              Reject
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}

function StatusPanel({ message }: { message: string }) {
  return (
    <div className="mt-5 rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-sm text-zinc-600">
      {message}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
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

function reviewErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message === "ADMIN_UNAUTHORIZED") {
    return "You are not authorized to review forms.";
  }
  if (error instanceof Error && error.message === "REVIEW_CONFLICT") {
    return "This form is no longer pending review.";
  }
  if (error instanceof Error && error.message === "REVIEW_NOT_FOUND") {
    return "This review item is no longer available.";
  }
  return "The review decision could not be submitted.";
}
