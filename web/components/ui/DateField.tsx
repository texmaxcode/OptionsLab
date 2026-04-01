"use client";

import { useRef, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "./cn";

type Props = {
  label: string;
  description?: string;
  icon?: ReactNode;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "type">;

const CalendarIcon = () => (
  <svg
    aria-hidden="true"
    className="h-4 w-4 text-zinc-400 dark:text-zinc-500"
    viewBox="0 0 20 20"
    fill="currentColor"
  >
    <path d="M6 2a1 1 0 011 1v1h6V3a1 1 0 112 0v1h1a1 1 0 011 1v11a1 1 0 01-1 1H3a1 1 0 01-1-1V5a1 1 0 011-1h1V3a1 1 0 011-1zm11 7H3v7h14V9z" />
  </svg>
);

export function DateField({
  label,
  description,
  className,
  icon,
  id: idProp,
  ...inputProps
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const id = idProp ?? `date-${label.replace(/\s+/g, "-").toLowerCase()}`;
  const disabled = Boolean(inputProps.disabled);

  const openPicker = () => {
    const input = inputRef.current;
    if (!input || disabled) return;
    if (typeof (input as HTMLInputElement & { showPicker?: () => void }).showPicker === "function") {
      (input as HTMLInputElement & { showPicker: () => void }).showPicker();
    } else {
      input.click();
    }
  };

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {label}
      </label>
      {description ? (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{description}</p>
      ) : null}
      <div className="relative">
        <input
          ref={inputRef}
          id={id}
          type="date"
          className={cn(
            "date-field-input w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 pl-3 pr-9 py-2 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 disabled:cursor-not-allowed disabled:bg-zinc-100 disabled:text-zinc-500 dark:disabled:bg-zinc-900 dark:disabled:text-zinc-500",
            className
          )}
          {...inputProps}
        />
        <button
          type="button"
          onClick={openPicker}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center rounded-r-lg text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-inset disabled:cursor-not-allowed disabled:hover:text-zinc-400 dark:disabled:hover:text-zinc-500"
          tabIndex={-1}
          aria-label={`Open calendar for ${label}`}
          disabled={disabled}
        >
          {icon ?? <CalendarIcon />}
        </button>
      </div>
    </div>
  );
}

