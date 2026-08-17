"use client";

import { useState } from "react";

import { inkFor } from "@/lib/answer";
import { INK } from "@/lib/ink";
import type { QuizQuestion } from "@/lib/types";

/** Quiz mode: questions written from the loaded material, each answer citable. */
export function QuizPanel({ questions, onClose }: { questions: QuizQuestion[]; onClose: () => void }) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const answered = Object.keys(answers).length;
  const correct = questions.filter((question, index) => answers[index] === question.correct_index).length;

  return (
    <aside
      role="dialog"
      aria-modal="true"
      aria-label="Quiz"
      className="fixed inset-0 z-20 flex justify-end bg-ink-950/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-[30rem] flex-col border-l border-line bg-ink-900"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line-soft px-5 py-4">
          <div>
            <h2 className="font-display text-[1.15rem] text-bright">Quiz</h2>
            <p className="label mt-0.5 text-quieter">
              {answered === questions.length
                ? `${correct} of ${questions.length} correct`
                : `${answered} of ${questions.length} answered`}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="control rounded-md border border-line px-3 py-1.5 text-quiet transition-colors hover:text-bright"
          >
            Close
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <ol className="flex flex-col gap-6">
            {questions.map((question, questionIndex) => {
              const chosen = answers[questionIndex];
              const isAnswered = chosen !== undefined;
              const ink = INK[inkFor(question.source_ref)];

              return (
                <li key={questionIndex}>
                  <p className="font-display text-[15px] leading-[1.5] text-bright">
                    <span className="label mr-2 text-quieter">{questionIndex + 1}</span>
                    {question.question}
                  </p>

                  <div className="mt-2.5 flex flex-col gap-1.5">
                    {question.options.map((option, optionIndex) => {
                      const isCorrect = optionIndex === question.correct_index;
                      const isChosen = chosen === optionIndex;

                      let tone = "border-line text-quiet hover:border-accent/60 hover:text-bright";
                      if (isAnswered && isCorrect) tone = "border-ok/70 bg-ok/10 text-bright";
                      else if (isChosen) tone = "border-bad/70 bg-bad/10 text-bright";
                      else if (isAnswered) tone = "border-line-soft text-quieter";

                      return (
                        <button
                          key={optionIndex}
                          type="button"
                          disabled={isAnswered}
                          onClick={() =>
                            setAnswers((current) => ({ ...current, [questionIndex]: optionIndex }))
                          }
                          className={`rounded-md border px-3 py-2 text-left text-[13px] leading-[1.45] transition-colors disabled:cursor-default ${tone}`}
                        >
                          {option}
                        </button>
                      );
                    })}
                  </div>

                  {isAnswered && (
                    <div className="mt-2 border-l-2 border-line pl-3">
                      <p className="text-[12.5px] leading-[1.55] text-quiet">{question.explanation}</p>
                      <p className={`label mt-1 ${ink.text}`}>
                        {question.source_ref} · {question.locator}
                      </p>
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </aside>
  );
}
