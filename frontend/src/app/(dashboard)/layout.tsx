import React from "react";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-[100dvh] w-screen overflow-hidden flex flex-col bg-[#111b21]">
      {children}
    </div>
  );
}
