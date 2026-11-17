"use client";

import React from "react";
import { Sparkles, Info, ShieldCheck } from "lucide-react";

export function AppHeader() {
  return (
    <header className="h-16 border-b border-rose-100/60 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-pink-400 via-rose-400 to-purple-400 flex items-center justify-center text-white shadow-sm shadow-pink-200">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm sm:text-base tracking-tight">
              HerAI
            </h1>
            <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-pink-50 dark:bg-pink-950/40 text-pink-600 dark:text-pink-400 border border-pink-200/60 dark:border-pink-900/40">
              <ShieldCheck className="w-3 h-3" />
              AI Simulation
            </span>
          </div>
          <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
            Modeled on authorized historical conversations
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-zinc-50 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 text-xs border border-zinc-200/70 dark:border-zinc-700">
          <Info className="w-3.5 h-3.5 text-zinc-400" />
          <span>Not a human</span>
        </div>
      </div>
    </header>
  );
}
