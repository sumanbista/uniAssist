"use client";

import { useState } from "react";

import { ToolTrace as ToolTraceData } from "@/lib/api";

type ToolTraceProps = {
  trace: ToolTraceData;
};

const STATUS_STYLES: Record<string, string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  fallback: "border-amber-200 bg-amber-50 text-amber-800",
  error: "border-red-200 bg-red-50 text-red-800",
};

function formatToolName(toolName: string | null): string {
  return toolName ?? "no_tool";
}

export function ToolTrace({ trace }: ToolTraceProps) {
  const [isOpen, setIsOpen] = useState(false);
  const statusClasses =
    STATUS_STYLES[trace.status] ?? "border-zinc-200 bg-zinc-50 text-zinc-700";

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 text-xs text-zinc-700">
      <button
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition hover:bg-zinc-100"
        onClick={() => setIsOpen((current) => !current)}
        type="button"
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className={`rounded-md border px-2 py-1 font-medium ${statusClasses}`}>
            {trace.status}
          </span>
          <span className="truncate font-medium text-zinc-800">
            {formatToolName(trace.tool_name)} used
          </span>
        </span>
        <span className="shrink-0 text-zinc-500">{isOpen ? "Hide" : "Inspect"}</span>
      </button>

      {isOpen ? (
        <div className="border-t border-zinc-200 px-3 py-3">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="font-medium text-zinc-500">Role</dt>
              <dd className="mt-1 text-zinc-900">{trace.role ?? "none"}</dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500">Authorized</dt>
              <dd className="mt-1 text-zinc-900">
                {trace.authorized ? "yes" : "no"}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500">Confidence</dt>
              <dd className="mt-1 text-zinc-900">
                {Math.round(trace.confidence * 100)}%
              </dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500">Execution time</dt>
              <dd className="mt-1 text-zinc-900">{trace.execution_time_ms}ms</dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500">Source</dt>
              <dd className="mt-1 text-zinc-900">{trace.source ?? "none"}</dd>
            </div>
            <div>
              <dt className="font-medium text-zinc-500">Tool</dt>
              <dd className="mt-1 text-zinc-900">{formatToolName(trace.tool_name)}</dd>
            </div>
            {trace.error_type ? (
              <div>
                <dt className="font-medium text-zinc-500">Error type</dt>
                <dd className="mt-1 text-zinc-900">{trace.error_type}</dd>
              </div>
            ) : null}
          </dl>

          {trace.message ? (
            <p className="mt-3 rounded-md border border-zinc-200 bg-white px-3 py-2 text-zinc-700">
              {trace.message}
            </p>
          ) : null}

          <div className="mt-3">
            <p className="font-medium text-zinc-500">Parameters</p>
            <pre className="mt-1 max-h-44 overflow-auto rounded-md bg-zinc-950 p-3 text-[11px] leading-5 text-zinc-50">
              {JSON.stringify(trace.parameters, null, 2)}
            </pre>
          </div>
        </div>
      ) : null}
    </div>
  );
}
