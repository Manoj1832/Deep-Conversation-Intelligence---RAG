import React from "react";
import { Sparkles } from "lucide-react";

export function TypingIndicator() {
  return (
    <div className="flex gap-3 mb-4 items-center">
      <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-pink-400 to-rose-400 flex items-center justify-center text-white shrink-0 shadow-xs">
        <Sparkles className="w-4 h-4 animate-spin-slow" />
      </div>
      <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-white dark:bg-zinc-900 border border-rose-100/70 dark:border-zinc-800 flex items-center gap-1.5 shadow-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-bounce" style={{ animationDelay: "0ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-bounce" style={{ animationDelay: "150ms" }} />
        <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-bounce" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  );
}
