import { Chat } from "@/components/Chat";

export default function Home() {
  return (
    <main className="min-h-screen bg-zinc-50 text-zinc-950">
      <section className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-4 py-6 sm:px-6 lg:py-10">
        <Chat />
      </section>
    </main>
  );
}
