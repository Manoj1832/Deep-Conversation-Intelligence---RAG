import React from "react";
import { formatTimestamp } from "@/lib/utils";
import { Sparkles, User } from "lucide-react";

interface MessageBubbleProps {
  role: "user" | "companion";
  content: string;
  timestamp: string;
}

export function MessageBubble({ role, content, timestamp }: MessageBubbleProps) {
  const isCompanion = role === "companion";

  return (
    <div className={`flex gap-3 mb-4 ${isCompanion ? "justify-start" : "justify-end"}`}>
      {isCompanion && (
        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-pink-400 to-rose-400 flex items-center justify-center text-white shrink-0 shadow-xs mt-1">
          <Sparkles className="w-4 h-4" />
        </div>
      )}

      <div className={`flex flex-col max-w-[85%] sm:max-w-[75%] ${isCompanion ? "items-start" : "items-end"}`}>
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed shadow-xs whitespace-pre-wrap break-words ${
            isCompanion
              ? "bg-white dark:bg-zinc-900 border border-rose-100/70 dark:border-zinc-800 text-zinc-800 dark:text-zinc-100 rounded-tl-sm"
              : "bg-rose-500 text-white rounded-tr-sm"
          }`}
        >
          {content}
        </div>
        {timestamp && (
          <span className="text-[10px] text-zinc-400 mt-1 px-1">
            {formatTimestamp(timestamp)}
          </span>
        )}
      </div>

      {!isCompanion && (
        <div className="w-8 h-8 rounded-full bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center text-zinc-600 dark:text-zinc-300 shrink-0 mt-1">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
}
