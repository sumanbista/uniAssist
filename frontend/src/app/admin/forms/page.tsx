import { AdminFormsDashboard } from "@/components/AdminFormsDashboard";

export default function AdminFormsPage() {
  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:py-10">
        <div>
          <p className="text-sm font-medium text-teal-700">Admin</p>
          <h1 className="text-3xl font-semibold">Forms governance</h1>
        </div>
        <AdminFormsDashboard />
      </section>
    </main>
  );
}
