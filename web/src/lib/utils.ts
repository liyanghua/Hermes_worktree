import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { Translations } from "@/i18n/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Mondwest font only — use on layout shells; do not force normal-case here or `text-display` chrome (Segmented, badges) stops uppercasing. */
export const themedFont = "font-mondwest";

/** Mondwest body copy — sentence-case themed text (not uppercase chrome). */
export const themedBody = "font-mondwest normal-case";

/** Mondwest brand chrome — uppercase section headers and nav labels. */
export const themedChrome = "font-mondwest text-display";

function formatRelativeTime(delta: number, time?: Translations["time"]): string {
  if (delta < 0 || Number.isNaN(delta)) return time?.unknown ?? "unknown";
  if (delta < 60) return time?.justNow ?? "just now";
  if (delta < 3600) {
    const count = Math.floor(delta / 60);
    return time?.minutesAgo?.replace("{count}", String(count)) ?? `${count}m ago`;
  }
  if (delta < 86400) {
    const count = Math.floor(delta / 3600);
    return time?.hoursAgo?.replace("{count}", String(count)) ?? `${count}h ago`;
  }
  if (delta < 172800) return time?.yesterday ?? "yesterday";
  const count = Math.floor(delta / 86400);
  return time?.daysAgo?.replace("{count}", String(count)) ?? `${count}d ago`;
}

/** Relative time from a Unix epoch timestamp (seconds). */
export function timeAgo(ts: number, time?: Translations["time"]): string {
  return formatRelativeTime(Date.now() / 1000 - ts, time);
}

/** Relative time from an ISO-8601 timestamp string. */
export function isoTimeAgo(iso: string, time?: Translations["time"]): string {
  return formatRelativeTime((Date.now() - new Date(iso).getTime()) / 1000, time);
}
