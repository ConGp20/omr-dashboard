"use client";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { CommandPalette } from "@/components/CommandPalette";
import { OnboardingTour } from "@/components/onboarding/OnboardingTour";
import { useStatusStream } from "@/hooks/useStatusStream";

/**
 * Client shell: starts the live status stream and renders the sidebar around
 * page content. The wizard and login routes render full-bleed (no sidebar).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const fullBleed = pathname === "/wizard" || pathname === "/login";
  // Don't open the authenticated event stream on the login screen — it would
  // just 401 in a loop while the user is trying to sign in.
  useStatusStream({ enabled: pathname !== "/login" });

  if (fullBleed) {
    return (
      <main className="min-h-screen">
        {children}
        <CommandPalette />
      </main>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      {/* pt accounts for the fixed mobile top bar (h-[52px]); md+ has no top bar. */}
      <main className="flex-1 overflow-x-hidden pt-[52px] md:ml-60 md:pt-0">
        <div className="mx-auto max-w-7xl p-4 md:p-6">{children}</div>
      </main>
      <CommandPalette />
      <OnboardingTour />
    </div>
  );
}
