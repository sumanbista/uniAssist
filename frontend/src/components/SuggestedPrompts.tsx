const PROMPTS = [
  "When is add/drop deadline?",
  "Who is the CS department chair?",
  "What registration events are available?",
  "When are holidays in Spring 2026?",
  "How do I register for classes?",
];

type SuggestedPromptsProps = {
  disabled?: boolean;
  onSelect: (prompt: string) => void;
};

export function SuggestedPrompts({ disabled = false, onSelect }: SuggestedPromptsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {PROMPTS.map((prompt) => (
        <button
          className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-left text-sm text-zinc-700 transition hover:border-teal-300 hover:bg-teal-50 hover:text-teal-900 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={disabled}
          key={prompt}
          onClick={() => onSelect(prompt)}
          type="button"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}
