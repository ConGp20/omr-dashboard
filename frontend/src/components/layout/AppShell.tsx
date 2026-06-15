"use client";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { useStatusStream } from "@/hooks/useStatusStream";

/**
 * Client shell: starts the live status stream and renders the sidebar around
 * page content. The wizard and login routes render full-bleed (no sidebar).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  useStatusStream();

  const fullBleed = pathname === "/wizard" || pathname === "/login";

  if (fullBleed) {
    return <main className="min-h-screen">{children}</main>;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden md:ml-60">
        <div className="mx-auto max-w-7xl p-4 md:p-6">{children}</div>
      </main>
    </div>
  );
}
