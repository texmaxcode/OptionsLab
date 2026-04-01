"use client";

import type { SelectHTMLAttributes, ReactNode } from "react";
import { cn } from "./cn";

const ChevronDown = () => (
  <svg
    aria-hidden="true"
    className="h-4 w-4 shrink-0 text-zinc-500 dark:text-zinc-400 pointer-events-none"
    viewBox="0 0 20 20"
    fill="currentColor"
  >
    <path
      fillRule="evenodd"
      d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z"
      clipRule="evenodd"
    />
  </svg>
);

type Props = {
  label: string;
  description?: string;
  children: ReactNode;
} & Omit<SelectHTMLAttributes<HTMLSelectElement>, "className"> & {
    className?: string;
  };

export function SelectField({
  label,
  description,
  className,
  children,
  id: idProp,
  ...selectProps
}: Props) {
  const id = idProp ?? `select-${label.replace(/\s+/g, "-").toLowerCase()}`;

  return (
    <div className="space-y-1.5">
      <label
        htmlFor={id}
        className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
      >
        {label}
      </label>
      {description ? (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{description}</p>
      ) : null}
      <div className="relative">
        <select
          id={id}
          className={cn(
            "w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 pl-3 pr-10 py-2 text-sm text-zinc-900 dark:text-zinc-100 appearance-none",
            className
          )}
          {...selectProps}
        >
          {children}
        </select>
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
          <ChevronDown />
        </span>
      </div>
    </div>
  );
}
