"use client";

import React, { useState, useEffect, useRef } from "react";
import { Send, Plus, RefreshCw, AlertCircle, HeartHandshake } from "lucide-react";
import { apiClient, ChatMessage, ChatSession } from "@/lib/api-client";
import { MessageBubble } from "@/components/chat/message-bubble";
import { TypingIndicator } from "@/components/chat/typing-indicator";

export function ChatWindow() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingTokenBuffer, setStreamingTokenBuffer] = useState("");
  const [retrievedMemories, setRetrievedMemories] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    if (activeSessionId) {
      loadMessages(activeSessionId);
    }
  }, [activeSessionId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingTokenBuffer]);

  const loadSessions = async () => {
    try {
      setError(null);
      const list = await apiClient.getChatSessions();
      setSessions(list);
      if (list.length > 0 && !activeSessionId) {
        setActiveSessionId(list[0].session_id);
      } else if (list.length === 0) {
        await handleNewSession();
      }
    } catch (err: any) {
      console.error(err);
      setError("Unable to connect to HerAI backend. Please ensure the backend is running.");
    }
  };

  const loadMessages = async (sid: string) => {
    try {
      setIsLoading(true);
      setError(null);
      const msgs = await apiClient.getSessionMessages(sid);
      setMessages(msgs);
    } catch (err: any) {
      console.error(err);
      setError("Failed to load messages for this conversation.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewSession = async () => {
    try {
      const newSess = await apiClient.createChatSession("Conversation with HerAI");
      setSessions((prev) => [newSess, ...prev]);
      setActiveSessionId(newSess.session_id);
      setMessages([]);
      setStreamingTokenBuffer("");
      setRetrievedMemories([]);
    } catch (err: any) {
      console.error(err);
      setError("Failed to start new conversation session.");
    }
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const text = inputValue.trim();
    if (!text || isStreaming || !activeSessionId) return;

    setInputValue("");
    setError(null);
    setRetrievedMemories([]);

    // Optimistic user message
    const optimisticUserMsg: ChatMessage = {
      id: "opt-" + Date.now(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUserMsg]);

    setIsStreaming(true);
    setStreamingTokenBuffer("");

    let accumulatedTokens = "";

    try {
      await apiClient.streamChat(
        activeSessionId,
        text,
        (token: string) => {
          accumulatedTokens += token;
          setStreamingTokenBuffer((prev) => prev + token);
        },
        (meta: any) => {
          if (meta.retrieved_memories) {
            setRetrievedMemories(meta.retrieved_memories);
          }
        }
      );

      // Finalize companion turn
      const finalCompanionMsg: ChatMessage = {
        id: "comp-" + Date.now(),
        role: "companion",
        content: accumulatedTokens,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, finalCompanionMsg]);
      setStreamingTokenBuffer("");
    } catch (err: any) {
      console.error("Streaming error:", err);
      setError("Streaming connection interrupted. You can retry sending your message.");
    } finally {
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex-1 flex flex-col h-[calc(100vh-8rem)] max-w-5xl mx-auto w-full bg-white dark:bg-zinc-900 rounded-2xl border border-rose-100/70 dark:border-zinc-800 shadow-sm overflow-hidden">
      {/* Session Top Bar */}
      <div className="px-4 py-3 border-b border-rose-100/60 dark:border-zinc-800 flex items-center justify-between bg-stone-50/50 dark:bg-zinc-950/50">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
            Active Companion Persona: Sakthi
          </span>
          {retrievedMemories.length > 0 && (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-300 border border-purple-200/50">
              <HeartHandshake className="w-3 h-3" />
              {retrievedMemories.length} Memories Activated
            </span>
          )}
        </div>

        <button
          onClick={handleNewSession}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-rose-50 dark:bg-zinc-800 text-rose-600 dark:text-rose-400 hover:bg-rose-100 dark:hover:bg-zinc-700 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Error Notice */}
      {error && (
        <div className="px-4 py-2.5 bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-300 text-xs flex items-center justify-between border-b border-rose-100 dark:border-rose-900/50">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => loadSessions()}
            className="underline font-medium hover:text-rose-800"
          >
            Retry
          </button>
        </div>
      )}

      {/* Message Area */}
      <div className="flex-1 p-4 sm:p-6 overflow-y-auto">
        {messages.length === 0 && !isStreaming && (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-zinc-400">
            <div className="w-12 h-12 rounded-full bg-rose-50 dark:bg-zinc-800 flex items-center justify-center text-rose-400 mb-3">
              <HeartHandshake className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-200 mb-1">
              Start conversing with HerAI
            </h3>
            <p className="text-xs max-w-sm text-zinc-500 leading-relaxed mb-4">
              Modeled after 24,971 historical messages, conversational habits, inside jokes, and shared memories.
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-md">
              {["Hi chello! Enna panra?", "Do you remember our Thiruchengode talk?", "Watched any good movies lately?"].map(
                (prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setInputValue(prompt);
                    }}
                    className="text-xs px-3 py-1.5 rounded-full bg-stone-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-rose-50 dark:hover:bg-zinc-700 hover:text-rose-600 transition-colors"
                  >
                    "{prompt}"
                  </button>
                )
              )}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role}
            content={m.content}
            timestamp={m.timestamp}
          />
        ))}

        {isStreaming && (
          <>
            {streamingTokenBuffer ? (
              <MessageBubble
                role="companion"
                content={streamingTokenBuffer}
                timestamp={new Date().toISOString()}
              />
            ) : (
              <TypingIndicator />
            )}
          </>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-3 sm:p-4 border-t border-rose-100/60 dark:border-zinc-800 bg-white dark:bg-zinc-900">
        <form onSubmit={handleSendMessage} className="flex gap-2 items-end">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message in English or Tanglish..."
            rows={1}
            disabled={isStreaming}
            className="flex-1 resize-none bg-stone-50 dark:bg-zinc-800/70 border border-zinc-200 dark:border-zinc-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-400 dark:focus:ring-rose-500 disabled:opacity-50 max-h-32 min-h-[42px]"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isStreaming}
            className="p-2.5 rounded-xl bg-rose-500 hover:bg-rose-600 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-xs"
            aria-label="Send message"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
