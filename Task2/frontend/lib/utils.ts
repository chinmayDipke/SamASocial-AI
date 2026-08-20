import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes so a caller's className always wins over a default. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
