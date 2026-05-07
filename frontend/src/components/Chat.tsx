"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { sendQuery } from "@/lib/api";
import { ChatMessage, MessageBubble } from "@/components/MessageBubble";
import { SuggestedPrompts } from "@/components/SuggestedPrompts";

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Ask me about deadlines, academic dates, campus events, contacts, or registration help.",
};

function createId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  async function submitQuery(query: string) {
    const trimmedQuery = query.trim();
    if (!trimmedQuery || isLoading) {
      return;
    }

    setErrorMessage("");
    setInput("");
    setIsLoading(true);
    setMessages((currentMessages) => [
      ...currentMessages,
      {
        id: createId("user"),
        role: "user",
        content: trimmedQuery,
      },
    ]);

    try {
      const response = await sendQuery(trimmedQuery);
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: createId("assistant"),
          role: "assistant",
          content: response.answer,
          status: response.status,
          toolUsed: response.tool_used,
          confidence: response.confidence,
          trace: response.trace,
        },
      ]);
    } catch {
      const friendlyError =
        "I could not reach the UniAssist backend. Check that FastAPI is running on localhost:8000.";
      setErrorMessage(friendlyError);
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          id: createId("assistant-error"),
          role: "assistant",
          content: friendlyError,
          status: "error",
          trace: {
            tool_name: null,
            confidence: 0,
            parameters: {},
            execution_time_ms: 0,
            status: "error",
            source: null,
            message: "Network request to the backend failed.",
          },
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitQuery(input);
  }

  return (
    <section className="flex min-h-[680px] w-full flex-col rounded-lg border border-zinc-200 bg-zinc-100 shadow-sm">
      <header className="border-b border-zinc-200 bg-white px-5 py-4">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-medium text-teal-700">UniAssist AI</p>
            <h1 className="text-2xl font-semibold text-zinc-950">University assistant</h1>
          </div>
          <p className="text-sm text-zinc-500">Connected to /query</p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-5">
        <div className="space-y-4">
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {isLoading ? (
            <article className="flex justify-start">
              <div className="rounded-lg border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-600 shadow-sm">
                Thinking...
              </div>
            </article>
          ) : null}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="border-t border-zinc-200 bg-white p-4 sm:p-5">
        <SuggestedPrompts disabled={isLoading} onSelect={submitQuery} />
        <form className="mt-4 flex gap-3" onSubmit={handleSubmit}>
          <label className="sr-only" htmlFor="query">
            Ask UniAssist
          </label>
          <textarea
            className="min-h-12 flex-1 resize-none rounded-lg border border-zinc-300 px-4 py-3 text-sm text-zinc-950 outline-none transition placeholder:text-zinc-400 focus:border-teal-500 focus:ring-2 focus:ring-teal-100 disabled:bg-zinc-100"
            disabled={isLoading}
            id="query"
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submitQuery(input);
              }
            }}
            placeholder="Ask about add/drop, registration, events, holidays, or contacts"
            rows={1}
            value={input}
          />
          <button
            className="h-12 rounded-lg bg-teal-700 px-5 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-zinc-300"
            disabled={isLoading || !input.trim()}
            type="submit"
          >
            Send
          </button>
        </form>
        {errorMessage ? (
          <p className="mt-3 text-sm text-red-700">{errorMessage}</p>
        ) : null}
      </div>
    </section>
  );
}
