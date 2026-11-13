/**
 * ===============================================================================
 * MODULE: utils.ts
 * PROJECT: OmniRAG Enterprise Agentic Support Chatbot
 * LAYER: Frontend Utility Layer (Tailwind Class Merger)
 * ===============================================================================
 * 
 * DESCRIPTION:
 *     Utility function combining `clsx` and `tailwind-merge` (`twMerge`) to safely 
 *     combine and deduplicate conditional Tailwind CSS class names across shadcn components.
 * ===============================================================================
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merges conditional class names and resolves conflicting Tailwind CSS classes.
 * 
 * @param inputs Variable array of class values (strings, objects, arrays, booleans).
 * @returns Merged single class string.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
