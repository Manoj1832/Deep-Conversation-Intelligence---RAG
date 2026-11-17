"use client";

import React, { useState } from "react";
import Link from "next/router";
import { usePathname, useRouter } from "next/navigation";
import {
  MessageSquare,
  History,
  BrainCircuit,
  HeartHandshake,
  Settings,
  LogOut,
  Menu,
  X,
  Sparkles
} from "lucide-react";
import { createClient } from "@/utils/supabase/client";

const navItems = [
  { href: "/chat", label: "Live Chat", icon: MessageSquare },
  { href: "/history", label: "Archive History", icon: History },
  { href: "/memories", label: "Memories", icon: HeartHandshake },
  { href: "/personality", label: "Personality", icon: BrainCircuit },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);

  const handleLogout = async () => {
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
      router.push("/login");
    } catch {
      router.push("/login");
    }
  };

  return (
    <>
      {/* Mobile Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="lg:hidden fixed bottom-5 right-5 z-50 p-3 rounded-full bg-rose-500 text-white shadow-lg hover:bg-rose-600 focus:outline-none"
        aria-label="Toggle navigation"
      >
        {isOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
      </button>

      {/* Backdrop */}
      {isOpen && (
        <div
          onClick={() => setIsOpen(false)}
          className="lg:hidden fixed inset-0 bg-black/40 backdrop-blur-sm z-40 transition-opacity"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-40 w-64 bg-stone-50/90 dark:bg-zinc-950/90 border-r border-rose-100/60 dark:border-zinc-800 flex flex-col justify-between transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="p-5">
          {/* Brand Logo */}
          <div className="flex items-center gap-3 mb-8 px-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-pink-400 via-rose-400 to-purple-400 flex items-center justify-center text-white shadow-sm shadow-pink-200">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <span className="font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight text-lg">
                HerAI
              </span>
              <span className="block text-[10px] text-zinc-400 font-mono tracking-wider">
                COMPANION V2.0
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href || (item.href !== "/chat" && pathname?.startsWith(item.href));
              return (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={() => setIsOpen(false)}
                  className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-rose-100/70 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 font-semibold shadow-xs"
                      : "text-zinc-600 dark:text-zinc-400 hover:bg-stone-100 dark:hover:bg-zinc-900 hover:text-zinc-900 dark:hover:text-zinc-100"
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? "text-rose-500" : "text-zinc-400"}`} />
                  {item.label}
                </a>
              );
            })}
          </nav>
        </div>

        {/* Footer & Logout */}
        <div className="p-4 border-t border-rose-100/60 dark:border-zinc-800">
          <div className="px-3 py-2.5 mb-2 rounded-lg bg-pink-50/60 dark:bg-zinc-900/60 border border-pink-100/60 dark:border-zinc-800 text-[11px] text-zinc-500 dark:text-zinc-400">
            <p className="font-medium text-pink-700 dark:text-pink-400 mb-0.5">Companion Mode</p>
            <p>Empirical Persona (Sakthi)</p>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2.5 px-3.5 py-2 rounded-lg text-sm text-zinc-600 dark:text-zinc-400 hover:bg-rose-50 dark:hover:bg-zinc-900 hover:text-rose-600 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>
    </>
  );
}
