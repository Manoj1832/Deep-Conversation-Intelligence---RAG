import React from "react";
import { WhatsAppChat } from "@/components/chat/whatsapp-chat";

export const metadata = {
  title: "Sakthi GPT",
  description: "WhatsApp chat simulation with Sakthi",
};

export default function ChatPage() {
  return <WhatsAppChat />;
}
