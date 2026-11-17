import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatTimestamp(isoStr: string): string {
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return "";
  }
}

export function formatDate(isoStr: string): string {
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return "";
  }
}
