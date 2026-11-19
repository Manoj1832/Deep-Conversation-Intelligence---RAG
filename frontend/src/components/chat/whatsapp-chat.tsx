"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Send,
  Mic,
  Smile,
  Paperclip,
  Search,
  MoreVertical,
  Phone,
  Video,
  CheckCheck,
  Lock,
  ChevronLeft,
  Pin,
  CircleDashed,
  MessageSquare,
  SmilePlus,
  Edit3,
  Check,
  X,
  Trash2,
  Image as ImageIcon,
  Sticker,
  Unlock,
  Archive,
  Clock,
  Calendar,
  Eye,
  AlertCircle
} from "lucide-react";
import { apiClient, ChatMessage, ChatSession, HistoricalSession, HistoricalMessage } from "@/lib/api-client";

function formatTime(isoString?: string): string {
  if (!isoString) return "";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", hour12: true });
  } catch {
    return "";
  }
}

const EMOJI_CATEGORIES = {
  favs: {
    label: "⭐ Favorites",
    emojis: ["🥺", "🙄", "😂", "❤️‍🩹", "😭", "😚", "😋", "🥱", "🤣", "🤗", "💖", "✨", "💔", "❤️", "🥰", "👍"],
  },
  smileys: {
    label: "😀 Smileys",
    emojis: [
      "😀", "😃", "😄", "😁", "😆", "😅", "🤣", "😂", "🙂", "🙃", "😉", "😊", "😇", "🥰", "😍", "🤩",
      "😘", "😗", "😚", "😙", "😋", "😛", "😜", "🤪", "😝", "🤑", "🤗", "🤭", "🤫", "🤔", "🤐", "🤨",
      "😐", "😑", "😶", "😏", "😒", "🙄", "😬", "🤥", "😌", "😔", "😪", "🤤", "😴", "😷", "🤒", "🤕"
    ],
  },
  gestures: {
    label: "👋 Gestures",
    emojis: ["👍", "👎", "👏", "🙌", "🤝", "🙏", "✌️", "🤞", "🤟", "🤘", "👌", "🤏", "👈", "👉", "👆", "👇", "☝️", "💪"],
  },
  hearts: {
    label: "❤️ Hearts",
    emojis: ["❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔", "❤️‍🩹", "❤️‍🔥", "💕", "💞", "💓", "💗", "💖", "💘", "💝"],
  },
  food: {
    label: "🍕 Food",
    emojis: ["🍕", "🍔", "🍟", "🥪", "🌮", "🍜", "🍱", "🍛", "🍙", "🍰", "🍦", "🍫", "☕", "🧋", "🥤", "🍩"],
  },
};

export function WhatsAppChat() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingTokenBuffer, setStreamingTokenBuffer] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [mobileShowChat, setMobileShowChat] = useState(true);
  const [isWarmingUp, setIsWarmingUp] = useState(false);

  // New Functionality States: Edit, Clear, Reactions, Emoji & Media Uploads
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [reactionPickerMessageId, setReactionPickerMessageId] = useState<string | null>(null);
  const [showClearChatModal, setShowClearChatModal] = useState(false);
  const [showTopMenu, setShowTopMenu] = useState(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const [activeEmojiCategory, setActiveEmojiCategory] = useState<keyof typeof EMOJI_CATEGORIES>("favs");

  // Secret Locked History Vault States ("kannachi")
  const [searchQuery, setSearchQuery] = useState("");
  const [isVaultUnlocked, setIsVaultUnlocked] = useState(false);
  const [historicalSessions, setHistoricalSessions] = useState<HistoricalSession[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [selectedHistoricalSession, setSelectedHistoricalSession] = useState<HistoricalSession | null>(null);
  const [historicalSessionMessages, setHistoricalSessionMessages] = useState<HistoricalMessage[]>([]);
  const [isLoadingHistoricalMessages, setIsLoadingHistoricalMessages] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    // Proactively pre-warm Render instance as soon as the page opens
    fetch("https://deep-conversation-intelligence-rag.onrender.com/health", { mode: "no-cors" }).catch(() => {});
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
      // If it takes more than 1.5s, Render is spinning up from cold sleep
      const timer = setTimeout(() => setIsWarmingUp(true), 1500);
      const list = await apiClient.getChatSessions();
      clearTimeout(timer);
      setIsWarmingUp(false);
      setSessions(list);
      if (list.length > 0) {
        setActiveSessionId(list[0].session_id);
      } else {
        await handleNewSession();
      }
    } catch (err: any) {
      console.error(err);
      setIsWarmingUp(true);
      setError("Connecting to Sakthi GPT backend...");
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
      setError("Failed to load conversation messages.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewSession = async () => {
    try {
      const newSess = await apiClient.createChatSession("Sakthi");
      setSessions((prev) => [newSess, ...prev]);
      setActiveSessionId(newSess.session_id);
      setMessages([]);
      setStreamingTokenBuffer("");
      setShowTopMenu(false);
    } catch (err: any) {
      console.error(err);
      setError("Failed to initialize session.");
    }
  };

  // 1. Clear Chat Functionality
  const handleClearChat = async () => {
    if (!activeSessionId) return;
    try {
      await apiClient.clearChatMessages(activeSessionId);
      setMessages([]);
      setShowClearChatModal(false);
      setShowTopMenu(false);
    } catch (err: any) {
      console.error(err);
      setError("Failed to clear chat messages.");
    }
  };

  // 2. Edit Message Functionality
  const startEditing = (m: ChatMessage) => {
    setEditingMessageId(m.id);
    setEditingContent(m.content);
    setReactionPickerMessageId(null);
  };

  const cancelEditing = () => {
    setEditingMessageId(null);
    setEditingContent("");
  };

  const saveEdit = async (messageId: string) => {
    const trimmed = editingContent.trim();
    if (!trimmed || !activeSessionId) return;
    try {
      await apiClient.editMessage(activeSessionId, messageId, trimmed);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, content: trimmed, edited: true } : m
        )
      );
      setEditingMessageId(null);
      setEditingContent("");
    } catch (err: any) {
      console.error(err);
      setError("Failed to update message.");
    }
  };

  // 3. Reaction Functionality
  const handleReact = async (messageId: string, emoji: string) => {
    if (!activeSessionId) return;
    setReactionPickerMessageId(null);
    try {
      const res = await apiClient.reactToMessage(activeSessionId, messageId, emoji);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId ? { ...m, reaction: res.reaction } : m
        )
      );
    } catch (err: any) {
      console.error(err);
      // Optimistic fallback
      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? { ...m, reaction: m.reaction === emoji ? null : emoji }
            : m
        )
      );
    }
  };

  // 4. Emoji Selection
  const handleEmojiSelect = (emoji: string) => {
    setInputValue((prev) => prev + emoji);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  // 5. Media & Emoji Upload Functionality
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !activeSessionId) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      const dataUrl = event.target?.result as string;
      const optimisticMediaMsg: ChatMessage = {
        id: "media-" + Date.now(),
        role: "user",
        content: file.name.endsWith(".gif") || file.size < 50000 ? "🎨 Sent a sticker / custom emoji" : "📷 Sent a photo",
        timestamp: new Date().toISOString(),
        media_url: dataUrl,
        media_type: file.name.endsWith(".gif") || file.size < 50000 ? "emoji_sticker" : "image"
      };

      setMessages((prev) => [...prev, optimisticMediaMsg]);
      setShowAttachMenu(false);

      // Trigger companion response to image
      setIsStreaming(true);
      setStreamingTokenBuffer("");
      let accumulatedTokens = "";

      try {
        await apiClient.streamChat(
          activeSessionId,
          `[Shared a photo / emoji sticker: ${file.name}]`,
          (token: string) => {
            accumulatedTokens += token;
            setStreamingTokenBuffer((prev) => prev + token);
          },
          () => {}
        );

        const finalCompanionMsg: ChatMessage = {
          id: "sakthi-" + Date.now(),
          role: "companion",
          content: accumulatedTokens || "Aww super da! 🥺❤️",
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, finalCompanionMsg]);
        setStreamingTokenBuffer("");
      } catch (streamErr) {
        console.error(streamErr);
        const finalCompanionMsg: ChatMessage = {
          id: "sakthi-" + Date.now(),
          role: "companion",
          content: "Aww semma da! 🥺❤️ nalla irukku",
          timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, finalCompanionMsg]);
      } finally {
        setIsStreaming(false);
      }
    };
    reader.readAsDataURL(file);
    // Reset file input
    e.target.value = "";
  };

  // 6. Secret Locked Vault Controller ("kannachi")
  const handleSearchChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);

    if (query.trim().toLowerCase() === "kannachi") {
      setIsVaultUnlocked(true);
      setIsLoadingHistory(true);
      try {
        const data = await apiClient.getHistoricalSessions(100, 0);
        setHistoricalSessions(data.sessions || []);
      } catch (err) {
        console.error("Failed to load historical sessions:", err);
      } finally {
        setIsLoadingHistory(false);
      }
    }
  };

  const closeVault = () => {
    setIsVaultUnlocked(false);
    setSearchQuery("");
    setSelectedHistoricalSession(null);
    setHistoricalSessionMessages([]);
  };

  const handleSelectHistoricalSession = async (sess: HistoricalSession) => {
    setSelectedHistoricalSession(sess);
    setIsLoadingHistoricalMessages(true);
    try {
      const msgs = await apiClient.getHistoricalSessionMessages(sess.session_id, 200);
      setHistoricalSessionMessages(msgs);
    } catch (err) {
      console.error("Failed to load historical session messages:", err);
    } finally {
      setIsLoadingHistoricalMessages(false);
    }
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const text = inputValue.trim();
    if (!text || isStreaming) return;

    // Ensure we have an active session ID; if not initialized yet, create/fallback to one
    let targetSessionId = activeSessionId;
    if (!targetSessionId) {
      try {
        const newSess = await apiClient.createChatSession("Sakthi");
        setSessions([newSess]);
        setActiveSessionId(newSess.session_id);
        targetSessionId = newSess.session_id;
      } catch (sessErr) {
        console.error("Session creation error:", sessErr);
        // Fallback session identifier so sending never gets silently dropped
        targetSessionId = "default-session";
        setActiveSessionId(targetSessionId);
      }
    }

    setInputValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setShowEmojiPicker(false);
    setShowAttachMenu(false);
    setError(null);

    const optimisticUserMsg: ChatMessage = {
      id: "user-" + Date.now(),
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
        targetSessionId,
        text,
        (token: string) => {
          accumulatedTokens += token;
          setStreamingTokenBuffer((prev) => prev + token);
        },
        () => {}
      );

      const finalCompanionMsg: ChatMessage = {
        id: "sakthi-" + Date.now(),
        role: "companion",
        content: accumulatedTokens,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, finalCompanionMsg]);
      setStreamingTokenBuffer("");
    } catch (err: any) {
      console.error("Streaming error:", err);
      setError("Connection interrupted. Please try again.");
    } finally {
      setIsStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Only send on Enter on desktop (when shift key is NOT held)
    // On mobile devices, Enter should insert a newline normally
    if (e.key === "Enter" && !e.shiftKey && window.innerWidth >= 768) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  const latestMessage = messages[messages.length - 1];
  const lastPreviewText = isStreaming
    ? "typing..."
    : latestMessage
    ? latestMessage.content
    : "seri da.. chello unkitta dhaa sollanum nu nenachen.. 🥺 😂";
  const lastPreviewTime = latestMessage
    ? formatTime(latestMessage.timestamp)
    : "12:35 AM";
  const isLastFromUser = latestMessage?.role === "user";

  return (
    <div className="h-[100dvh] w-screen flex overflow-hidden bg-[#efeae2] dark:bg-[#0c1317]">
      {/* Hidden file input for emoji & photo uploads */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        accept="image/*"
        className="hidden"
      />

      {/* Clear Chat Confirmation Modal */}
      {showClearChatModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="bg-white dark:bg-[#202c33] rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-[#e9edef] dark:border-[#2a3942] space-y-4">
            <div className="flex items-center gap-3 text-[#ea4335]">
              <div className="p-2.5 rounded-full bg-red-100 dark:bg-red-950/50">
                <Trash2 className="w-5 h-5" />
              </div>
              <h3 className="text-base font-semibold text-[#111b21] dark:text-[#e9edef]">
                Clear this chat?
              </h3>
            </div>
            <p className="text-sm text-[#54656f] dark:text-[#8696a0] leading-relaxed">
              This will clear all messages in this conversation with Sakthi. This cannot be undone.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setShowClearChatModal(false)}
                className="px-4 py-2 rounded-xl text-sm font-medium text-[#54656f] dark:text-[#8696a0] hover:bg-[#f0f2f5] dark:hover:bg-[#2a3942] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleClearChat}
                className="px-4 py-2 rounded-xl text-sm font-medium bg-[#ea4335] hover:bg-[#d93025] text-white shadow-xs transition-colors"
              >
                Clear chat
              </button>
            </div>
          </div>
        </div>
      )}

      {/* WhatsApp Web Left Sidebar */}
      <div
        className={`w-full md:w-[380px] lg:w-[420px] h-full flex flex-col bg-white dark:bg-[#111b21] border-r border-[#e9edef] dark:border-[#222d34] shrink-0 z-20 ${
          mobileShowChat ? "hidden md:flex" : "flex"
        }`}
      >
        {/* Left Sidebar Header */}
        <div className="h-[60px] bg-[#f0f2f5] dark:bg-[#202c33] px-4 flex items-center justify-between border-b border-[#e9edef] dark:border-[#222d34] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[#00a884] to-[#25d366] text-white flex items-center justify-center font-bold text-sm shadow-xs tracking-wider">
              SG
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="font-semibold text-[15px] text-[#111b21] dark:text-[#e9edef] tracking-tight">
                  Sakthi GPT
                </span>
                <span className="w-2 h-2 rounded-full bg-[#00a884]" title="Active" />
              </div>
              <span className="text-[11px] text-[#667781] dark:text-[#8696a0]">WhatsApp Simulation</span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-[#54656f] dark:text-[#aebac1]">
            <button className="hover:text-[#111b21] dark:hover:text-white transition-colors" title="Status" aria-label="Status">
              <CircleDashed className="w-5 h-5" />
            </button>
            <button className="hover:text-[#111b21] dark:hover:text-white transition-colors" title="New Chat" aria-label="New Chat" onClick={handleNewSession}>
              <MessageSquare className="w-5 h-5" />
            </button>
            <button className="hover:text-[#111b21] dark:hover:text-white transition-colors" title="Menu" aria-label="Menu" onClick={() => setShowTopMenu(!showTopMenu)}>
              <MoreVertical className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Search Bar with Secret Passphrase Detection */}
        <div className="p-2 border-b border-[#e9edef] dark:border-[#222d34] bg-white dark:bg-[#111b21]">
          <div className="bg-[#f0f2f5] dark:bg-[#202c33] rounded-lg h-[35px] flex items-center px-3 gap-3 focus-within:ring-1 focus-within:ring-[#00a884] transition-all">
            <Search className="w-4 h-4 text-[#54656f] dark:text-[#8696a0] shrink-0" aria-hidden="true" />
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearchChange}
              placeholder="Search or enter secret vault passphrase..."
              aria-label="Search conversations or enter secret vault passphrase"
              className="bg-transparent text-[13px] text-[#111b21] dark:text-[#e9edef] placeholder:text-[#8696a0] focus:outline-none w-full"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                aria-label="Clear search input"
                className="text-[#8696a0] hover:text-[#111b21] dark:hover:text-[#e9edef]"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Chat List - Only One Chat: Sakthi */}
        <div className="flex-1 overflow-y-auto whatsapp-scrollbar bg-white dark:bg-[#111b21]">
          <div
            onClick={() => setMobileShowChat(true)}
            className="flex items-center gap-3 px-3 py-3 bg-[#f0f2f5] dark:bg-[#2a3942] cursor-pointer hover:bg-[#f5f6f6] dark:hover:bg-[#2a3942] transition-colors relative"
          >
            {/* Sakthi Profile Avatar */}
            <div className="relative shrink-0">
              <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-[#ff6b81] to-[#ff4757] flex items-center justify-center text-white font-semibold text-lg shadow-xs">
                S
              </div>
              <span className="absolute bottom-0 right-0 w-3.5 h-3.5 bg-[#00a884] border-2 border-white dark:border-[#202c33] rounded-full" />
            </div>

            {/* Content Preview */}
            <div className="flex-1 min-w-0 pr-1">
              <div className="flex items-center justify-between mb-0.5">
                <span className="font-semibold text-[16px] text-[#111b21] dark:text-[#e9edef] truncate">
                  Sakthi
                </span>
                <span className="text-[12px] text-[#00a884] font-medium shrink-0 ml-2">
                  {lastPreviewTime}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 min-w-0 text-[13px] text-[#667781] dark:text-[#8696a0] truncate">
                  {isLastFromUser && (
                    <CheckCheck className="w-4 h-4 text-[#53bdeb] shrink-0" />
                  )}
                  {isStreaming ? (
                    <span className="text-[#00a884] font-medium animate-pulse">typing...</span>
                  ) : (
                    <span className="truncate">{lastPreviewText}</span>
                  )}
                </div>
                <Pin className="w-3.5 h-3.5 text-[#8696a0] shrink-0 ml-2 fill-current rotate-45 opacity-60" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* WhatsApp Web Right Chat View */}
      <div
        className={`flex-1 h-full flex flex-col min-w-0 z-10 relative ${
          mobileShowChat ? "flex" : "hidden md:flex"
        }`}
      >
        {/* Chat Top Header */}
        <div className="h-[60px] bg-[#f0f2f5] dark:bg-[#202c33] px-3 sm:px-4 flex items-center justify-between border-b border-[#e9edef] dark:border-[#222d34] shrink-0 z-20 relative">
          <div className="flex items-center gap-3 min-w-0">
            {/* Back button on mobile */}
            <button
              onClick={() => setMobileShowChat(false)}
              className="md:hidden text-[#54656f] dark:text-[#aebac1] hover:text-[#111b21] p-1"
              aria-label="Back to chat list"
            >
              <ChevronLeft className="w-6 h-6" />
            </button>

            <div className="relative shrink-0 cursor-pointer">
              <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-[#ff6b81] to-[#ff4757] text-white flex items-center justify-center font-semibold text-base shadow-xs">
                S
              </div>
              <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-[#00a884] border-2 border-white dark:border-[#202c33] rounded-full" />
            </div>

            <div className="min-w-0 cursor-pointer">
              <div className="flex items-center gap-1.5">
                <h2 className="font-semibold text-[16px] text-[#111b21] dark:text-[#e9edef] leading-tight truncate">
                  Sakthi
                </h2>
              </div>
              <p className="text-[12px] leading-tight truncate">
                {isStreaming ? (
                  <span className="text-[#00a884] font-medium animate-pulse">typing...</span>
                ) : isWarmingUp ? (
                  <span className="text-amber-500 font-medium animate-pulse">connecting server...</span>
                ) : (
                  <span className="text-[#667781] dark:text-[#8696a0]">online</span>
                )}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 sm:gap-4 text-[#54656f] dark:text-[#aebac1] relative">
            <button className="hover:text-[#111b21] dark:hover:text-white transition-colors" title="Video Call" aria-label="Video Call">
              <Video className="w-5 h-5" />
            </button>
            <button className="hover:text-[#111b21] dark:hover:text-white transition-colors" title="Voice Call" aria-label="Voice Call">
              <Phone className="w-5 h-5" />
            </button>
            <button className="hover:text-[#111b21] dark:hover:text-white transition-colors" title="Search in chat" aria-label="Search in chat">
              <Search className="w-5 h-5" />
            </button>
            <button
              onClick={() => setShowTopMenu(!showTopMenu)}
              className="hover:text-[#111b21] dark:hover:text-white transition-colors p-1"
              title="Menu"
              aria-label="Chat menu options"
              aria-expanded={showTopMenu}
            >
              <MoreVertical className="w-5 h-5" />
            </button>

            {/* Top Dropdown Menu */}
            {showTopMenu && (
              <div className="absolute right-0 top-10 w-48 bg-white dark:bg-[#202c33] rounded-xl shadow-xl border border-[#e9edef] dark:border-[#2a3942] py-1.5 z-50 text-sm animate-in fade-in zoom-in-95 duration-100">
                <button
                  onClick={() => {
                    setShowTopMenu(false);
                    setShowClearChatModal(true);
                  }}
                  className="w-full px-4 py-2.5 text-left text-red-600 dark:text-red-400 hover:bg-[#f0f2f5] dark:hover:bg-[#2a3942] flex items-center gap-2.5 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Clear chat</span>
                </button>
                <button
                  onClick={() => {
                    setShowTopMenu(false);
                    handleNewSession();
                  }}
                  className="w-full px-4 py-2.5 text-left text-[#111b21] dark:text-[#e9edef] hover:bg-[#f0f2f5] dark:hover:bg-[#2a3942] flex items-center gap-2.5 transition-colors"
                >
                  <MessageSquare className="w-4 h-4" />
                  <span>New session</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* WhatsApp Chat Canvas */}
        <div
          onClick={() => {
            setShowTopMenu(false);
            setReactionPickerMessageId(null);
            setShowAttachMenu(false);
          }}
          className="whatsapp-chat-bg flex-1 overflow-y-auto px-3 sm:px-10 md:px-16 lg:px-20 py-4 space-y-2 whatsapp-scrollbar flex flex-col justify-between"
        >
          <div className="space-y-2">
            {/* WhatsApp Security / Simulation Disclaimer Pill */}
            <div className="flex justify-center my-3">
              <div className="bg-[#ffeecd] dark:bg-[#182229] text-[#54656f] dark:text-[#8696a0] text-[12px] px-3.5 py-1.5 rounded-lg max-w-lg text-center shadow-[0_1px_0.5px_rgba(11,20,26,.13)] leading-relaxed flex items-center justify-center gap-1.5 select-none">
                <Lock className="w-3.5 h-3.5 shrink-0 text-[#54656f] dark:text-[#8696a0]" />
                <span>
                  Messages are generated by Sakthi GPT simulation modeled on historical WhatsApp conversations. Not an actual human.
                </span>
              </div>
            </div>

            {/* Date Separator Pill */}
            <div className="flex justify-center my-2">
              <span className="bg-white dark:bg-[#182229] text-[#54656f] dark:text-[#8696a0] text-[11px] font-medium px-3 py-1 rounded-md uppercase tracking-wider shadow-[0_1px_0.5px_rgba(11,20,26,.13)] select-none">
                TODAY
              </span>
            </div>

            {/* Empty State Prompt */}
            {messages.length === 0 && !isStreaming && (
              <div className="flex justify-start my-2">
                <div className="relative max-w-[85%] sm:max-w-[70%] bg-white dark:bg-[#202c33] text-[#111b21] dark:text-[#e9edef] rounded-lg rounded-tl-none px-3 py-1.5 shadow-[0_1px_0.5px_rgba(11,20,26,.13)]">
                  <span className="text-[14.2px] leading-[19px]">
                    Hi chello! Enna panra?
                  </span>
                  <span className="text-[11px] text-[#667781] dark:text-[#8696a0] ml-2 inline-block float-right mt-1 pt-0.5 select-none">
                    12:35 AM
                  </span>
                </div>
              </div>
            )}

            {/* Error Notification */}
            {error && (
              <div className="flex justify-center my-2">
                <div className="bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 text-xs px-3 py-1 rounded-md shadow-xs flex items-center gap-2">
                  <span>{error}</span>
                </div>
              </div>
            )}

            {/* Message Bubble Feed */}
            {messages.map((m) => {
              const isPartner = m.role === "companion";
              const isEditingThis = editingMessageId === m.id;
              const isPickerOpen = reactionPickerMessageId === m.id;

              return (
                <div
                  key={m.id}
                  className={`flex ${isPartner ? "justify-start" : "justify-end"} mb-2 group relative items-end`}
                >
                  {/* Partner side actions */}
                  {isPartner && (
                    <div className="opacity-70 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity flex items-center gap-1 mb-1 mr-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setReactionPickerMessageId(isPickerOpen ? null : m.id);
                        }}
                        className="p-1 rounded-full text-[#8696a0] hover:text-[#111b21] dark:hover:text-[#e9edef] hover:bg-black/5 dark:hover:bg-white/10"
                        title="React"
                      >
                        <SmilePlus className="w-4 h-4" />
                      </button>
                    </div>
                  )}

                  {/* Bubble Container */}
                  <div
                    className={`relative max-w-[85%] sm:max-w-[70%] md:max-w-[65%] rounded-lg px-3 py-1.5 shadow-[0_1px_0.5px_rgba(11,20,26,.13)] text-[#111b21] dark:text-[#e9edef] ${
                      isPartner
                        ? "bg-white dark:bg-[#202c33] rounded-tl-none"
                        : "bg-[#d9fdd3] dark:bg-[#005c4b] rounded-tr-none"
                    }`}
                  >
                    {/* Reaction Bar Popup */}
                    {isPickerOpen && (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        className={`absolute -top-10 ${
                          isPartner ? "left-0" : "right-0"
                        } z-40 flex items-center gap-1.5 bg-white dark:bg-[#202c33] rounded-full px-2.5 py-1 shadow-lg border border-[#e9edef] dark:border-[#2a3942] animate-in fade-in zoom-in-95 duration-100`}
                      >
                        {["👍", "❤️", "😂", "😮", "😢", "🙏", "🥺"].map((em) => (
                          <button
                            key={em}
                            onClick={() => handleReact(m.id, em)}
                            className="hover:scale-130 active:scale-95 transition-transform text-lg px-0.5 leading-none"
                          >
                            {em}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Media / Photo attachment */}
                    {m.media_url && (
                      <div className="mb-1 rounded-md overflow-hidden max-w-sm">
                        <img
                          src={m.media_url}
                          alt="Attachment"
                          className="w-full max-h-72 object-cover rounded-md"
                        />
                      </div>
                    )}

                    {/* Message Text or Inline Edit Mode */}
                    {isEditingThis ? (
                      <div className="flex flex-col gap-1.5 min-w-[220px] py-1">
                        <textarea
                          value={editingContent}
                          onChange={(e) => setEditingContent(e.target.value)}
                          className="w-full bg-white/90 dark:bg-black/30 text-[14.2px] leading-[19px] p-2 rounded-md border border-[#00a884] focus:outline-none resize-none"
                          rows={2}
                          autoFocus
                        />
                        <div className="flex items-center justify-end gap-1.5 pt-0.5">
                          <button
                            onClick={cancelEditing}
                            className="px-2 py-1 rounded text-[#54656f] dark:text-[#8696a0] hover:bg-black/10 text-xs flex items-center gap-1"
                          >
                            <X className="w-3.5 h-3.5" /> Cancel
                          </button>
                          <button
                            onClick={() => saveEdit(m.id)}
                            className="px-2.5 py-1 rounded bg-[#00a884] text-white text-xs font-medium flex items-center gap-1 shadow-xs hover:bg-[#008f72]"
                          >
                            <Check className="w-3.5 h-3.5" /> Save
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <span className="text-[14.2px] leading-[19px] whitespace-pre-wrap break-words inline">
                          {m.content}
                        </span>
                        {m.edited && (
                          <span className="text-[10px] text-[#667781] dark:text-[#8696a0] italic ml-1 select-none">
                            edited
                          </span>
                        )}
                        <span
                          className={`text-[11px] text-[#667781] dark:text-[#8696a0] ml-2 inline-flex items-center gap-1 float-right mt-1 pt-0.5 select-none`}
                        >
                          {formatTime(m.timestamp)}
                          {!isPartner && (
                            <CheckCheck className="w-3.5 h-3.5 text-[#53bdeb]" />
                          )}
                        </span>
                      </>
                    )}

                    {/* Reaction Badge on bubble */}
                    {m.reaction && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleReact(m.id, m.reaction!);
                        }}
                        className={`absolute -bottom-2.5 ${
                          isPartner ? "right-2" : "left-2"
                        } bg-white dark:bg-[#202c33] border border-[#e9edef] dark:border-[#2a3942] rounded-full px-1.5 py-0.5 text-xs shadow-xs flex items-center gap-0.5 hover:scale-110 active:scale-95 transition-transform cursor-pointer`}
                        title="Click to remove reaction"
                      >
                        <span>{m.reaction}</span>
                      </button>
                    )}
                  </div>

                  {/* User side actions (React & Edit) */}
                  {!isPartner && !isEditingThis && (
                    <div className="opacity-70 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity flex items-center gap-0.5 mb-1 ml-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          startEditing(m);
                        }}
                        className="p-1 rounded-full text-[#8696a0] hover:text-[#111b21] dark:hover:text-[#e9edef] hover:bg-black/5 dark:hover:bg-white/10"
                        title="Edit message"
                      >
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setReactionPickerMessageId(isPickerOpen ? null : m.id);
                        }}
                        className="p-1 rounded-full text-[#8696a0] hover:text-[#111b21] dark:hover:text-[#e9edef] hover:bg-black/5 dark:hover:bg-white/10"
                        title="React"
                      >
                        <SmilePlus className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Live Streaming Bubble */}
            {isStreaming && (
              <div className="flex justify-start mb-2">
                <div className="relative max-w-[85%] sm:max-w-[70%] md:max-w-[65%] bg-white dark:bg-[#202c33] text-[#111b21] dark:text-[#e9edef] rounded-lg rounded-tl-none px-3 py-1.5 shadow-[0_1px_0.5px_rgba(11,20,26,.13)]">
                  {streamingTokenBuffer ? (
                    <>
                      <span className="text-[14.2px] leading-[19px] whitespace-pre-wrap break-words inline">
                        {streamingTokenBuffer}
                      </span>
                      <span className="text-[11px] text-[#667781] dark:text-[#8696a0] ml-2 inline-block float-right mt-1 pt-0.5 select-none">
                        {formatTime(new Date().toISOString())}
                      </span>
                    </>
                  ) : (
                    <div className="flex items-center gap-1 py-1 px-1">
                      <span className="w-2 h-2 rounded-full bg-[#8696a0] animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-2 h-2 rounded-full bg-[#8696a0] animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-2 h-2 rounded-full bg-[#8696a0] animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  )}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* WhatsApp Emoji Picker Drawer */}
        {showEmojiPicker && (
          <div className="bg-[#f0f2f5] dark:bg-[#202c33] border-t border-[#e9edef] dark:border-[#222d34] p-3 animate-in slide-in-from-bottom-2 duration-150 z-30 shrink-0">
            {/* Category Tabs */}
            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-[#e9edef] dark:border-[#2a3942] overflow-x-auto whatsapp-scrollbar">
              {(Object.keys(EMOJI_CATEGORIES) as Array<keyof typeof EMOJI_CATEGORIES>).map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveEmojiCategory(cat)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors shrink-0 ${
                    activeEmojiCategory === cat
                      ? "bg-[#00a884] text-white"
                      : "text-[#54656f] dark:text-[#8696a0] hover:bg-black/5 dark:hover:bg-white/10"
                  }`}
                >
                  {EMOJI_CATEGORIES[cat].label}
                </button>
              ))}
            </div>

            {/* Emoji Grid */}
            <div className="grid grid-cols-7 sm:grid-cols-10 md:grid-cols-14 gap-1.5 max-h-48 overflow-y-auto whatsapp-scrollbar py-1">
              {EMOJI_CATEGORIES[activeEmojiCategory].emojis.map((em, idx) => (
                <button
                  key={idx}
                  onClick={() => handleEmojiSelect(em)}
                  className="p-1.5 text-2xl hover:scale-125 active:scale-95 transition-transform text-center rounded-md hover:bg-black/5 dark:hover:bg-white/10 cursor-pointer"
                >
                  {em}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* WhatsApp Attachment Popover Menu */}
        {showAttachMenu && (
          <div className="absolute bottom-16 left-12 z-40 bg-white dark:bg-[#202c33] rounded-2xl shadow-xl border border-[#e9edef] dark:border-[#2a3942] p-2 space-y-1 animate-in zoom-in-95 duration-100">
            <button
              onClick={() => {
                fileInputRef.current?.click();
              }}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-[#f0f2f5] dark:hover:bg-[#2a3942] text-sm text-[#111b21] dark:text-[#e9edef] transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-[#007bfc] text-white flex items-center justify-center">
                <ImageIcon className="w-4 h-4" />
              </div>
              <span>Photos & Media</span>
            </button>
            <button
              onClick={() => {
                fileInputRef.current?.click();
              }}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-[#f0f2f5] dark:hover:bg-[#2a3942] text-sm text-[#111b21] dark:text-[#e9edef] transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-[#ff007a] text-white flex items-center justify-center">
                <Sticker className="w-4 h-4" />
              </div>
              <span>Custom Emoji / Sticker</span>
            </button>
          </div>
        )}

        {/* WhatsApp Bottom Input Bar */}
        <div className="min-h-[62px] bg-[#f0f2f5] dark:bg-[#202c33] px-3 sm:px-4 py-2 flex items-center gap-2 sm:gap-3 border-t border-[#e9edef] dark:border-[#222d34] shrink-0 relative pb-[max(0.5rem,env(safe-area-inset-bottom))]">
          <button
            type="button"
            onClick={() => {
              setShowEmojiPicker(!showEmojiPicker);
              setShowAttachMenu(false);
            }}
            className={`transition-colors p-1 rounded-full ${
              showEmojiPicker
                ? "text-[#00a884]"
                : "text-[#54656f] dark:text-[#8696a0] hover:text-[#111b21] dark:hover:text-[#e9edef]"
            }`}
            title="Emoji Picker"
          >
            <Smile className="w-6 h-6" />
          </button>
          <button
            type="button"
            onClick={() => {
              setShowAttachMenu(!showAttachMenu);
              setShowEmojiPicker(false);
            }}
            className={`transition-colors p-1 rounded-full ${
              showAttachMenu
                ? "text-[#00a884]"
                : "text-[#54656f] dark:text-[#8696a0] hover:text-[#111b21] dark:hover:text-[#e9edef]"
            }`}
            title="Attach Media / Emoji"
          >
            <Paperclip className="w-5 h-5" />
          </button>

          <div className="flex-1 bg-white dark:bg-[#2a3942] rounded-lg px-4 py-2 flex items-center shadow-[0_1px_0.5px_rgba(11,20,26,.13)]">
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              placeholder="Type a message"
              rows={1}
              disabled={isStreaming}
              className="w-full bg-transparent text-[15px] text-[#111b21] dark:text-[#e9edef] placeholder:text-[#8696a0] focus:outline-none resize-none max-h-24 leading-normal"
            />
          </div>

          {inputValue.trim() ? (
            <button
              type="button"
              disabled={isStreaming}
              onClick={handleSendMessage}
              onTouchEnd={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="w-10 h-10 rounded-full bg-[#00a884] hover:bg-[#008f72] flex items-center justify-center text-white shrink-0 shadow-sm active:scale-95 transition-all cursor-pointer"
              aria-label="Send message"
            >
              <Send className="w-4 h-4 ml-0.5 pointer-events-none" />
            </button>
          ) : (
            <button
              type="button"
              className="p-2 text-[#54656f] dark:text-[#8696a0] hover:text-[#111b21] dark:hover:text-[#e9edef] transition-colors"
              aria-label="Voice note"
            >
              <Mic className="w-6 h-6" />
            </button>
          )}
        </div>
      </div>

      {/* =========================================================================
          SECRET LOCKED VAULT MODAL (Unlocked via "kannachi" in search bar)
         ========================================================================= */}
      {isVaultUnlocked && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-2 sm:p-4 animate-in fade-in duration-200">
          <div className="bg-[#f0f2f5] dark:bg-[#111b21] rounded-2xl w-full max-w-4xl h-[90vh] flex flex-col shadow-2xl border border-[#e9edef] dark:border-[#222d34] overflow-hidden">
            {/* Vault Header */}
            <div className="bg-[#202c33] text-white px-5 py-4 flex items-center justify-between border-b border-[#2a3942] shrink-0">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/40">
                  <Unlock className="w-5 h-5 animate-pulse" />
                </div>
                <div>
                  <h3 className="font-semibold text-base flex items-center gap-2">
                    Secret Chat History Vault
                    <span className="text-[11px] bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-500/30">
                      Unlocked: &quot;kannachi&quot;
                    </span>
                  </h3>
                  <p className="text-xs text-gray-400">
                    Browse ground-truth historical WhatsApp sessions & unredacted chronological messages
                  </p>
                </div>
              </div>

              <button
                onClick={closeVault}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/20 hover:bg-red-500/30 text-red-300 text-xs font-medium transition-all"
              >
                <Lock className="w-3.5 h-3.5" />
                Lock & Close
              </button>
            </div>

            {/* Vault Body */}
            <div className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
              {/* Left Column: Historical Sessions */}
              <div className={`w-full md:w-80 border-r border-[#e9edef] dark:border-[#222d34] flex flex-col bg-white dark:bg-[#111b21] shrink-0 ${
                selectedHistoricalSession ? "hidden md:flex" : "flex"
              }`}>
                <div className="p-3 bg-[#f0f2f5] dark:bg-[#202c33] border-b border-[#e9edef] dark:border-[#222d34] flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#54656f] dark:text-[#8696a0] uppercase tracking-wider">
                    Past Sessions ({historicalSessions.length})
                  </span>
                  {isLoadingHistory && (
                    <span className="text-xs text-[#00a884] animate-pulse">Loading...</span>
                  )}
                </div>

                <div className="flex-1 overflow-y-auto whatsapp-scrollbar divide-y divide-[#e9edef] dark:divide-[#222d34]">
                  {historicalSessions.length === 0 && !isLoadingHistory && (
                    <div className="p-4 text-center text-xs text-[#8696a0]">
                      No historical sessions found.
                    </div>
                  )}

                  {historicalSessions.map((sess) => {
                    const isSelected = selectedHistoricalSession?.session_id === sess.session_id;
                    const startDate = new Date(sess.start_timestamp).toLocaleDateString([], {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    });
                    const startTime = new Date(sess.start_timestamp).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    });

                    return (
                      <div
                        key={sess.session_id}
                        onClick={() => handleSelectHistoricalSession(sess)}
                        className={`p-3 cursor-pointer transition-colors ${
                          isSelected
                            ? "bg-[#00a884]/15 border-l-4 border-[#00a884]"
                            : "hover:bg-[#f5f6f6] dark:hover:bg-[#202c33]"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-semibold text-[#111b21] dark:text-[#e9edef] flex items-center gap-1">
                            <Calendar className="w-3.5 h-3.5 text-[#00a884]" />
                            {startDate}
                          </span>
                          <span className="text-[11px] text-[#8696a0]">{startTime}</span>
                        </div>
                        <div className="flex items-center justify-between text-[11px] text-[#667781] dark:text-[#8696a0]">
                          <span>{sess.message_count} messages</span>
                          <span className="text-emerald-500 font-mono text-[10px]">
                            {sess.partner_message_count} Sakthi / {sess.user_message_count} Manoj
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Historical Messages Viewer */}
              <div className={`flex-1 flex flex-col bg-[#efeae2] dark:bg-[#0b141a] min-w-0 ${
                !selectedHistoricalSession ? "hidden md:flex" : "flex"
              }`}>
                {selectedHistoricalSession ? (
                  <>
                    <div className="p-3 bg-white dark:bg-[#202c33] border-b border-[#e9edef] dark:border-[#222d34] flex items-center justify-between shrink-0">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setSelectedHistoricalSession(null)}
                          className="md:hidden p-1 rounded-full text-[#54656f] dark:text-[#aebac1] hover:bg-black/5"
                          title="Back to sessions"
                        >
                          <ChevronLeft className="w-5 h-5" />
                        </button>
                        <div>
                          <div className="text-xs font-semibold text-[#111b21] dark:text-[#e9edef]">
                            Session {selectedHistoricalSession.session_id.substring(0, 8)}...
                          </div>
                          <div className="text-[11px] text-[#8696a0]">
                            {new Date(selectedHistoricalSession.start_timestamp).toLocaleString()} –{" "}
                            {new Date(selectedHistoricalSession.end_timestamp).toLocaleTimeString()}
                          </div>
                        </div>
                      </div>
                      <div className="text-xs font-medium text-[#00a884] bg-[#00a884]/10 px-2 py-1 rounded">
                        {historicalSessionMessages.length} Messages
                      </div>
                    </div>

                    <div className="flex-1 overflow-y-auto p-4 space-y-2 whatsapp-scrollbar">
                      {isLoadingHistoricalMessages ? (
                        <div className="flex items-center justify-center h-full text-sm text-[#8696a0]">
                          Loading conversation records...
                        </div>
                      ) : historicalSessionMessages.length === 0 ? (
                        <div className="flex items-center justify-center h-full text-sm text-[#8696a0]">
                          No messages in this session.
                        </div>
                      ) : (
                        historicalSessionMessages.map((msg) => {
                          const isUser = msg.sender === "user" || msg.original_sender === "Manoj";
                          const isSystem = msg.is_system_message || msg.message_type === "system";

                          if (isSystem) {
                            return (
                              <div key={msg.id} className="flex justify-center my-2">
                                <span className="bg-[#ffeecd] dark:bg-[#182229] text-[#54656f] dark:text-[#8696a0] text-[11px] px-3 py-1 rounded-md max-w-md text-center shadow-xs">
                                  {msg.body}
                                </span>
                              </div>
                            );
                          }

                          return (
                            <div
                              key={msg.id}
                              className={`flex ${isUser ? "justify-end" : "justify-start"} my-1`}
                            >
                              <div
                                className={`max-w-[75%] rounded-lg px-3 py-1.5 shadow-xs relative text-[13px] ${
                                  isUser
                                    ? "bg-[#d9fdd3] dark:bg-[#005c4b] text-[#111b21] dark:text-[#e9edef] rounded-tr-none"
                                    : "bg-white dark:bg-[#202c33] text-[#111b21] dark:text-[#e9edef] rounded-tl-none"
                                }`}
                              >
                                <div className="text-[10px] font-bold text-[#00a884] dark:text-emerald-400 mb-0.5">
                                  {isUser ? "Manoj" : "Sakthi"}
                                </div>
                                <div className="whitespace-pre-wrap leading-relaxed select-text">
                                  {msg.body}
                                </div>
                                <div className="text-[10px] text-[#667781] dark:text-[#8696a0] text-right mt-0.5">
                                  {new Date(msg.timestamp).toLocaleTimeString([], {
                                    hour: "2-digit",
                                    minute: "2-digit",
                                  })}
                                </div>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-[#8696a0]">
                    <Archive className="w-12 h-12 mb-3 opacity-30 text-[#00a884]" />
                    <p className="text-sm font-medium text-[#111b21] dark:text-[#e9edef]">
                      Select a Session
                    </p>
                    <p className="text-xs max-w-sm mt-1">
                      Choose any session on the left to read chronological ground-truth messages between Manoj and Sakthi.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
