"use client";

import React from "react";
import { RelationshipMemory } from "@/lib/api-client";
import { Check, X, Trash2, Calendar, Tag, ShieldCheck, Clock } from "lucide-react";

interface MemoryCardProps {
  memory: RelationshipMemory;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onDelete: (id: string) => void;
}

export function MemoryCard({ memory, onApprove, onReject, onDelete }: MemoryCardProps) {
  const isApproved = memory.verification_status === "approved";
  const isPending = memory.verification_status === "pending_review";
  const isRejected = memory.verification_status === "rejected";

  return (
    <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-zinc-900 border border-rose-100/70 dark:border-zinc-800 shadow-xs flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 capitalize">
            <Tag className="w-3 h-3" />
            {memory.category.replace("_", " ")}
          </span>

          <span
            className={`text-[11px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1 ${
              isApproved
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400"
                : isPending
                ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400"
                : "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-400"
            }`}
          >
            {isApproved && <ShieldCheck className="w-3 h-3" />}
            {isPending && <Clock className="w-3 h-3" />}
            {memory.verification_status.replace("_", " ")}
          </span>
        </div>

        <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-1.5">
          {memory.title}
        </h4>
        <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed mb-3">
          {memory.description}
        </p>

        <div className="space-y-1 text-[11px] text-zinc-400">
          {memory.event_date && (
            <div className="flex items-center gap-1.5">
              <Calendar className="w-3 h-3 text-zinc-400" />
              <span>Event Date: {memory.event_date}</span>
            </div>
          )}
          <div className="flex items-center justify-between pt-1">
            <span>Confidence: {Math.round(memory.confidence * 100)}%</span>
            <span>{memory.source_message_ids.length} Source Message(s)</span>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between pt-3 mt-3 border-t border-zinc-100 dark:border-zinc-800">
        <div className="flex items-center gap-1.5">
          {isPending && (
            <>
              <button
                onClick={() => onApprove(memory.memory_id)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-emerald-50 hover:bg-emerald-100 text-emerald-700 transition-colors"
                title="Approve Memory"
              >
                <Check className="w-3.5 h-3.5" />
                Approve
              </button>
              <button
                onClick={() => onReject(memory.memory_id)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-red-50 hover:bg-red-100 text-red-700 transition-colors"
                title="Reject Memory"
              >
                <X className="w-3.5 h-3.5" />
                Reject
              </button>
            </>
          )}
        </div>

        <button
          onClick={() => {
            if (confirm("Are you sure you want to delete this memory? It will be removed from vector search.")) {
              onDelete(memory.memory_id);
            }
          }}
          className="p-1.5 rounded-lg text-zinc-400 hover:text-red-600 hover:bg-red-50 transition-colors"
          title="Delete Memory"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
