import { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import { adviseDeck } from '../../api/decks';
import type { DeckAdviseResponse } from '../../api/types';

interface AdvisePanelProps {
  /** The deck ID to ask questions about */
  deckId: number;
}

interface QAPair {
  question: string;
  answer: string;
  provider?: string;
}

/**
 * AI advisor panel for a specific deck.
 * Maintains a conversation history of Q&A pairs.
 * Renders AI responses using react-markdown.
 *
 * Usage:
 *   <AdvisePanel deckId={42} />
 */
export default function AdvisePanel({ deckId }: AdvisePanelProps) {
  const [question, setQuestion] = useState('');
  const [provider, setProvider] = useState('');
  const [history, setHistory] = useState<QAPair[]>([]);
  const conversationEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { mutate: ask, isPending, error, reset } = useMutation<
    DeckAdviseResponse,
    Error,
    { question: string; provider?: string }
  >({
    mutationFn: ({ question: q, provider: p }) =>
      adviseDeck(deckId, q, p || undefined),
    onSuccess: (data, variables) => {
      setHistory((prev) => [
        ...prev,
        {
          question: variables.question,
          answer: data.advice,
          provider: variables.provider,
        },
      ]);
      setQuestion('');
      reset();
    },
  });

  // Scroll to the latest answer when history updates
  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isPending) return;
    ask({ question: trimmed, provider: provider || undefined });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const trimmed = question.trim();
      if (trimmed && !isPending) {
        ask({ question: trimmed, provider: provider || undefined });
      }
    }
  };

  return (
    <section
      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-alt)]"
      aria-label="AI Deck Advisor"
    >
      {/* Panel header */}
      <div className="border-b border-[var(--color-border)] px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
          <SparkleIcon />
          Ask AI About This Deck
        </h2>
        <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
          Ask about improvements, synergies, card choices, or strategy.
        </p>
      </div>

      {/* Conversation history */}
      {history.length > 0 && (
        <div
          className="max-h-96 overflow-y-auto px-4 py-3 space-y-5"
          role="log"
          aria-live="polite"
          aria-label="Conversation history"
        >
          {history.map((pair, i) => (
            <ConversationEntry key={i} pair={pair} />
          ))}

          {/* Loading placeholder while waiting for next answer */}
          {isPending && (
            <div className="space-y-1">
              <QuestionBubble text={question} />
              <AnswerSkeleton />
            </div>
          )}

          <div ref={conversationEndRef} />
        </div>
      )}

      {/* Loading state when no history yet */}
      {isPending && history.length === 0 && (
        <div className="px-4 py-3 space-y-1">
          <QuestionBubble text={question} />
          <AnswerSkeleton />
        </div>
      )}

      {/* Error state */}
      {error && (
        <div
          role="alert"
          className="mx-4 mt-3 rounded-md border border-[var(--color-budget-over)] bg-red-950/40 p-3 text-sm text-[var(--color-budget-over)]"
        >
          <strong className="block font-semibold">Error</strong>
          {isLLMUnavailableError(error)
            ? 'No LLM provider is configured. Please configure an AI provider in Settings.'
            : error.message}
        </div>
      )}

      {/* Input form */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-[var(--color-border)] p-4 space-y-3"
        aria-label="Ask a question"
      >
        <div>
          <label htmlFor={`advise-question-${deckId}`} className="sr-only">
            Your question about this deck
          </label>
          <textarea
            ref={inputRef}
            id={`advise-question-${deckId}`}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What improvements would you suggest?"
            rows={2}
            disabled={isPending}
            aria-describedby="advise-hint"
            className={[
              'w-full resize-none rounded-lg border border-[var(--color-border)]',
              'bg-[var(--color-surface)] px-3 py-2 text-sm',
              'text-[var(--color-text-primary)] placeholder:text-[var(--color-text-secondary)]',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
              'disabled:opacity-50 transition-colors',
            ].join(' ')}
          />
          <p id="advise-hint" className="mt-1 text-xs text-[var(--color-text-secondary)]">
            Press Enter to submit, Shift+Enter for new line.
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <label
              htmlFor={`advise-provider-${deckId}`}
              className="text-xs text-[var(--color-text-secondary)] whitespace-nowrap"
            >
              Provider:
            </label>
            <select
              id={`advise-provider-${deckId}`}
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              disabled={isPending}
              className={[
                'rounded-md border border-[var(--color-border)] bg-[var(--color-surface)]',
                'px-2 py-1.5 text-xs text-[var(--color-text-primary)]',
                'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
                'disabled:opacity-50',
              ].join(' ')}
            >
              <option value="">Auto</option>
              <option value="anthropic">Anthropic (Claude)</option>
              <option value="openai">OpenAI (GPT)</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={!question.trim() || isPending}
            aria-busy={isPending}
            className={[
              'ml-auto rounded-lg px-4 py-2 text-sm font-semibold transition-colors',
              'bg-[var(--color-accent)] text-white',
              'hover:bg-[var(--color-accent-hover)]',
              'disabled:cursor-not-allowed disabled:opacity-40',
              'focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]',
            ].join(' ')}
          >
            {isPending ? (
              <span className="flex items-center gap-2">
                <SpinnerIcon />
                Asking...
              </span>
            ) : (
              'Ask'
            )}
          </button>
        </div>
      </form>
    </section>
  );
}

// ---------------------------------------------------------------------------
// ConversationEntry — renders a single Q&A pair
// ---------------------------------------------------------------------------

function ConversationEntry({ pair }: { pair: QAPair }) {
  return (
    <div className="space-y-2">
      <QuestionBubble text={pair.question} />
      <div className="rounded-lg bg-[var(--color-surface-raised)] px-3 py-3">
        <div className="mb-1.5 flex items-center gap-1.5">
          <SparkleIcon className="h-3 w-3 text-[var(--color-accent)]" />
          <span className="text-xs font-medium text-[var(--color-accent)]">AI Advisor</span>
        </div>
        <div className="prose-sm max-w-none text-sm text-[var(--color-text-primary)] leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:my-1 [&_ul]:pl-4 [&_li]:my-0.5 [&_strong]:text-[var(--color-text-primary)] [&_code]:rounded [&_code]:bg-[var(--color-surface)] [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-xs">
          <ReactMarkdown>{pair.answer}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// QuestionBubble
// ---------------------------------------------------------------------------

function QuestionBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-lg bg-[var(--color-accent)]/20 border border-[var(--color-accent)]/30 px-3 py-2">
        <p className="text-sm text-[var(--color-text-primary)]">{text}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AnswerSkeleton — loading shimmer while waiting for AI response
// ---------------------------------------------------------------------------

function AnswerSkeleton() {
  return (
    <div className="rounded-lg bg-[var(--color-surface-raised)] px-3 py-3">
      <div className="mb-2 flex items-center gap-1.5">
        <SpinnerIcon />
        <span className="text-xs text-[var(--color-text-secondary)]">Thinking...</span>
      </div>
      <div className="space-y-2">
        <div className="h-3 w-full animate-pulse rounded bg-[var(--color-border)]" />
        <div className="h-3 w-4/5 animate-pulse rounded bg-[var(--color-border)]" />
        <div className="h-3 w-2/3 animate-pulse rounded bg-[var(--color-border)]" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function SparkleIcon({ className = 'h-4 w-4 text-[var(--color-accent)]' }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6L12 2z" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg
      className="h-3 w-3 animate-spin text-[var(--color-text-secondary)]"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v8H4z"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Error helpers
// ---------------------------------------------------------------------------

function isLLMUnavailableError(error: Error): boolean {
  const msg = error.message.toLowerCase();
  return (
    msg.includes('no provider') ||
    msg.includes('not configured') ||
    msg.includes('provider unavailable') ||
    msg.includes('llm') ||
    msg.includes('api key') ||
    // HTTP 503 or 424
    msg.includes('503') ||
    msg.includes('424')
  );
}
