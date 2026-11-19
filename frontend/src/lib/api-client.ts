import { createClient } from "@/utils/supabase/client";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  (typeof window !== "undefined" ? "/api/backend" : "https://deep-conversation-intelligence-rag.onrender.com/api/v1");

export interface ChatMessage {
  id: string;
  role: "user" | "companion";
  content: string;
  timestamp: string;
  edited?: boolean;
  reaction?: string | null;
  media_url?: string | null;
  media_type?: "image" | "emoji_sticker" | null;
}

export interface ChatSession {
  session_id: string;
  title: string;
  created_at: string;
  last_message: string;
}

export interface RelationshipMemory {
  memory_id: string;
  category: string;
  title: string;
  description: string;
  event_date: string | null;
  confidence: number;
  verification_status: "approved" | "pending_review" | "rejected";
  source_message_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface PersonalityProfile {
  profile_id: string;
  version: string;
  participant: string;
  total_messages_analyzed: number;
  language_patterns: {
    total_words_analyzed: number;
    top_colloquial_vocabulary: Array<{ word: string; count: number }>;
    observed_greetings: Record<string, number>;
    observed_signoffs: Record<string, number>;
  };
  message_patterns: {
    average_character_length: number;
    average_burst_messages: number;
    median_response_latency_seconds: number;
    lowercase_start_percentage: number;
    trailing_ellipsis_percentage: number;
    question_percentage: number;
  };
  emoji_patterns: Array<{ emoji: string; count: number }>;
  communication_styles: {
    tone: string;
    dialect: string;
    formality_score: number;
  };
  confidence: number;
  review_status: string;
}

export interface PersonalityObservation {
  observation_id: string;
  dimension: string;
  observation: string;
  supporting_evidence: string;
  source_message_ids: string[];
  confidence: number;
  verification_status: string;
}

export interface HistoricalSession {
  session_id: string;
  start_timestamp: string;
  end_timestamp: string;
  message_count: number;
  partner_message_count: number;
  user_message_count: number;
  source_archive_ids: string[];
}

export interface HistoricalMessage {
  id: string;
  timestamp: string;
  sender: "partner" | "user" | "system";
  original_sender: string;
  body: string;
  message_type: string;
  media_type: string;
  is_multiline: boolean;
  source_line_number: number;
  is_system_message?: boolean;
}

class ApiClient {
  private async getAuthHeaders(): Promise<HeadersInit> {
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }
      return headers;
    } catch {
      return { "Content-Type": "application/json" };
    }
  }

  // --- Live Chat Endpoints ---
  async getChatSessions(): Promise<ChatSession[]> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/chat/sessions`, { headers, cache: "no-store" });
    if (!res.ok) throw new Error("Failed to load chat sessions");
    const data = await res.json();
    return data.sessions || [];
  }

  async createChatSession(title: string = "Conversation with HerAI"): Promise<ChatSession> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
      method: "POST",
      headers,
      body: JSON.stringify({ title }),
    });
    if (!res.ok) throw new Error("Failed to create chat session");
    return res.json();
  }

  async getSessionMessages(sessionId: string): Promise<ChatMessage[]> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages`, {
      headers,
      cache: "no-store",
    });
    if (!res.ok) throw new Error("Failed to load session messages");
    const data = await res.json();
    return data.messages || [];
  }

  async clearChatMessages(sessionId: string, pin: string = "1206"): Promise<void> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages?pin=${encodeURIComponent(pin)}`, {
      method: "DELETE",
      headers,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "Failed to clear chat messages");
    }
  }

  async editMessage(sessionId: string, messageId: string, content: string): Promise<{ status: string; message_id: string; content: string }> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages/${messageId}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ content }),
    });
    if (!res.ok) throw new Error("Failed to edit message");
    return res.json();
  }

  async reactToMessage(sessionId: string, messageId: string, emoji: string): Promise<{ status: string; message_id: string; reaction: string | null }> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages/${messageId}/reactions`, {
      method: "POST",
      headers,
      body: JSON.stringify({ emoji }),
    });
    if (!res.ok) throw new Error("Failed to react to message");
    return res.json();
  }

  async deleteMessage(sessionId: string, messageId: string): Promise<void> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages/${messageId}`, {
      method: "DELETE",
      headers,
    });
    if (!res.ok) throw new Error("Failed to delete message");
  }

  // SSE Chat Streaming
  async streamChat(
    sessionId: string,
    message: string,
    onToken: (token: string) => void,
    onMetadata?: (meta: any) => void,
    onMemoryLearned?: (memory: any) => void
  ): Promise<void> {
    const headers = await this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/chat/stream`, {
      method: "POST",
      headers,
      body: JSON.stringify({ session_id: sessionId, message }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`Failed to stream chat: ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let currentEvent = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.replace("event: ", "").trim();
        } else if (line.startsWith("data: ")) {
          const rawData = line.replace("data: ", "").trim();
          try {
            const parsed = JSON.parse(rawData);
            if (currentEvent === "token" && parsed.text) {
              onToken(parsed.text);
            } else if (currentEvent === "metadata" && onMetadata) {
              onMetadata(parsed);
            } else if (currentEvent === "memory_learned" && onMemoryLearned) {
              onMemoryLearned(parsed.memory);
            }
          } catch {
            // Non-JSON or raw text
            if (currentEvent === "token") onToken(rawData);
          }
        }
      }
    }
  }

  // --- Memories Endpoints ---
  async getMemories(category?: string, status?: string): Promise<RelationshipMemory[]> {
    const headers = await this.getAuthHeaders();
    const params = new URLSearchParams();
    if (category) params.append("category", category);
    if (status) params.append("status", status);

    const url = `${API_BASE_URL}/memories${params.toString() ? `?${params.toString()}` : ""}`;
    const res = await fetch(url, { headers, cache: "no-store" });
    if (!res.ok) throw new Error("Failed to load memories");
    const data = await res.json();
    return data.memories || [];
  }

  async approveMemory(memoryId: string): Promise<RelationshipMemory> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/memories/${memoryId}/approve`, {
      method: "POST",
      headers,
    });
    if (!res.ok) throw new Error("Failed to approve memory");
    return res.json();
  }

  async rejectMemory(memoryId: string, reason: string = ""): Promise<RelationshipMemory> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/memories/${memoryId}/reject`, {
      method: "POST",
      headers,
      body: JSON.stringify({ reason }),
    });
    if (!res.ok) throw new Error("Failed to reject memory");
    return res.json();
  }

  async deleteMemory(memoryId: string): Promise<void> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/memories/${memoryId}`, {
      method: "DELETE",
      headers,
    });
    if (!res.ok) throw new Error("Failed to delete memory");
  }

  // --- Personality Endpoints ---
  async getPersonalityProfile(): Promise<PersonalityProfile> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/personality`, { headers, cache: "no-store" });
    if (!res.ok) throw new Error("Failed to load personality profile");
    return res.json();
  }

  async getPersonalityObservations(): Promise<PersonalityObservation[]> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/personality/observations`, { headers, cache: "no-store" });
    if (!res.ok) throw new Error("Failed to load observations");
    const data = await res.json();
    return data.observations || [];
  }

  // --- History Endpoints ---
  async getHistoricalSessions(limit: number = 50, offset: number = 0): Promise<{ total: number; sessions: HistoricalSession[] }> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/history/sessions?limit=${limit}&offset=${offset}`, {
      headers,
      cache: "no-store",
    });
    if (!res.ok) throw new Error("Failed to load historical sessions");
    return res.json();
  }

  async getHistoricalSessionMessages(sessionId: string, limit: number = 100): Promise<HistoricalMessage[]> {
    const headers = await this.getAuthHeaders();
    const res = await fetch(`${API_BASE_URL}/history/sessions/${sessionId}/messages?limit=${limit}`, {
      headers,
      cache: "no-store",
    });
    if (!res.ok) throw new Error("Failed to load historical messages");
    const data = await res.json();
    return data.messages || [];
  }
}

export const apiClient = new ApiClient();
