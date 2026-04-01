"use client";

import type { HTMLAttributes } from "react";
import { cn } from "./cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl bg-white dark:bg-zinc-900 shadow-sm ring-1 ring-zinc-900/5 dark:ring-white/10",
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("px-3 py-3 sm:px-4 sm:py-3", className)} {...props} />
  );
}

export function CardBody({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("px-3 py-3 sm:px-4 sm:py-3", className)}
      {...props}
    />
  );
}

