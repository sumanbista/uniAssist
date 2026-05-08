"use client";

import { useEffect, useState } from "react";

import {
  AnalyticsSummary,
  RecentQueryLog,
  UserRole,
  fetchAnalyticsRoles,
  fetchAnalyticsSummary,
  fetchAnalyticsTools,
  fetchRecentQueries,
} from "@/lib/api";
import { RoleSwitcher } from "@/components/RoleSwitcher";

type AnalyticsState = {
  summary: AnalyticsSummary | null;
  tools: Record<string, number>;
  roles: Record<string, number>;
  recent: RecentQueryLog[];
};

const EMPTY_STATE: AnalyticsState = {
  summary: null,
  tools: {},
  roles: {},
  recent: [],
};

export function AnalyticsDashboard() {
  const [role, setRole] = useState<UserRole>("admin");
  const [analytics, setAnalytics] = useState<AnalyticsState>(EMPTY_STATE);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadAnalytics() {
      setIsLoading(true);
      setErrorMessage("");
      try {
        const [summary, tools, roles, recent] = await Promise.all([
          fetchAnalyticsSummary(role),
          fetchAnalyticsTools(role),
          fetchAnalyticsRoles(role),
          fetchRecentQueries(role),
        ]);

        if (isMounted) {
          setAnalytics({ summary, tools, roles, recent });
        }
      } catch (error) {
        if (isMounted) {
          setAnalytics(EMPTY_STATE);
          setErrorMessage(
            error instanceof Error
              ? error.message
              : "Unable to load analytics.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadAnalytics();

    return () => {
      isMounted = false;
    };
  }, [role]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium text-zinc-950">Analytics access role</p>
          <p className="text-sm text-zinc-500">
            Only admin can view persisted query analytics.
          </p>
        </div>
        <RoleSwitcher value={role} onChange={setRole} />
      </div>

      {errorMessage ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {errorMessage}
        </div>
      ) : null}

      {isLoading ? (
        <div className="rounded-lg border border-zinc-200 bg-white p-6 text-sm text-zinc-600">
          Loading analytics...
        </div>
      ) : null}

      {analytics.summary ? (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Total queries" value={analytics.summary.total_queries} />
            <MetricCard
              label="Avg latency"
              value={`${analytics.summary.average_latency_ms}ms`}
            />
            <MetricCard
              label="Fallback rate"
              value={`${Math.round(analytics.summary.fallback_rate * 100)}%`}
            />
            <MetricCard
              label="Most used tool"
              value={analytics.summary.most_used_tool ?? "none"}
            />
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <CountPanel title="Tool usage" counts={analytics.tools} />
            <CountPanel title="Queries by role" counts={analytics.roles} />
          </section>

          <RecentQueriesTable rows={analytics.recent} />
        </>
      ) : null}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <article className="rounded-lg border border-zinc-200 bg-white p-5">
      <p className="text-sm font-medium text-zinc-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-zinc-950">{value}</p>
    </article>
  );
}

function CountPanel({
  title,
  counts,
}: {
  title: string;
  counts: Record<string, number>;
}) {
  const entries = Object.entries(counts);
  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="mt-4 space-y-3">
        {entries.length ? (
          entries.map(([name, count]) => (
            <div className="flex items-center justify-between gap-4" key={name}>
              <span className="text-sm text-zinc-700">{name}</span>
              <span className="rounded-md bg-zinc-100 px-2 py-1 text-sm font-medium">
                {count}
              </span>
            </div>
          ))
        ) : (
          <p className="text-sm text-zinc-500">No data yet.</p>
        )}
      </div>
    </section>
  );
}

function RecentQueriesTable({ rows }: { rows: RecentQueryLog[] }) {
  return (
    <section className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
      <div className="border-b border-zinc-200 p-5">
        <h2 className="text-lg font-semibold">Recent queries</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-zinc-200 text-sm">
          <thead className="bg-zinc-50 text-left text-zinc-500">
            <tr>
              <th className="px-4 py-3 font-medium">Query</th>
              <th className="px-4 py-3 font-medium">Tool</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Confidence</th>
              <th className="px-4 py-3 font-medium">Latency</th>
              <th className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {rows.length ? (
              rows.map((row) => (
                <tr key={row.id}>
                  <td className="max-w-xs px-4 py-3 text-zinc-900">{row.query}</td>
                  <td className="px-4 py-3 text-zinc-700">{row.tool_used ?? "none"}</td>
                  <td className="px-4 py-3 text-zinc-700">{row.role ?? "none"}</td>
                  <td className="px-4 py-3 text-zinc-700">
                    {Math.round(row.confidence * 100)}%
                  </td>
                  <td className="px-4 py-3 text-zinc-700">{row.latency_ms}ms</td>
                  <td className="px-4 py-3">
                    <span className="rounded-md bg-zinc-100 px-2 py-1 text-zinc-700">
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="px-4 py-6 text-center text-zinc-500" colSpan={6}>
                  No query logs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
