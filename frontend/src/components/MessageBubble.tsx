import { ToolTrace as ToolTraceData } from "@/lib/api";
import { ToolTrace } from "@/components/ToolTrace";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: string;
  toolUsed?: string | null;
  confidence?: number;
  trace?: ToolTraceData;
};

type MessageBubbleProps = {
  message: ChatMessage;
};

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const bubbleClasses = isUser
    ? "bg-teal-700 text-white"
    : message.status === "error"
      ? "border border-red-200 bg-red-50 text-red-950"
      : message.status === "fallback"
        ? "border border-amber-200 bg-amber-50 text-amber-950"
      : "border border-zinc-200 bg-white text-zinc-950";

  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[82%] rounded-lg px-4 py-3 shadow-sm ${bubbleClasses}`}>
        <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        {!isUser && message.toolUsed ? (
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-zinc-500">
            <span className="rounded-md bg-zinc-100 px-2 py-1">
              {message.toolUsed}
            </span>
            {typeof message.confidence === "number" ? (
              <span className="rounded-md bg-zinc-100 px-2 py-1">
                {Math.round(message.confidence * 100)}% confidence
              </span>
            ) : null}
          </div>
        ) : null}
        {!isUser && message.trace ? (
          <FreshnessIndicator lastUpdated={message.trace.last_updated} />
        ) : null}
        {!isUser && message.trace ? <ToolTrace trace={message.trace} /> : null}
      </div>
    </article>
  );
}

function FreshnessIndicator({ lastUpdated }: { lastUpdated?: string | null }) {
  if (!lastUpdated) {
    return (
      <p className="mt-3 rounded-md bg-zinc-100 px-3 py-2 text-xs text-zinc-600">
        Responses are generated from structured university data.
      </p>
    );
  }

  const updatedDate = new Date(`${lastUpdated}T00:00:00`);
  const today = new Date();
  const ageMs = today.getTime() - updatedDate.getTime();
  const ageDays = Math.max(0, Math.floor(ageMs / 86_400_000));
  const isStale = ageDays > 7;
  const label =
    ageDays === 0
      ? "Updated today"
      : `Updated ${ageDays} ${ageDays === 1 ? "day" : "days"} ago`;

  return (
    <p
      className={`mt-3 rounded-md px-3 py-2 text-xs ${
        isStale ? "bg-amber-100 text-amber-900" : "bg-zinc-100 text-zinc-600"
      }`}
    >
      {label}. Responses are generated from structured university data.
    </p>
  );
}
