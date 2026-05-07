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
        {!isUser && message.trace ? <ToolTrace trace={message.trace} /> : null}
      </div>
    </article>
  );
}
