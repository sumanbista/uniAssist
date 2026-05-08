import { AnalyticsDashboard } from "@/components/AnalyticsDashboard";

export default function AdminAnalyticsPage() {
  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:py-10">
        <div>
          <p className="text-sm font-medium text-teal-700">Admin</p>
          <h1 className="text-3xl font-semibold">Query analytics</h1>
        </div>
        <AnalyticsDashboard />
      </section>
    </main>
  );
}
