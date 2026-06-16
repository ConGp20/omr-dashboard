"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Moon, Sun, Menu, X, Network, Compass, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDashboardStore } from "@/lib/store";
import { NAV } from "@/lib/nav";
import { requestTour } from "@/components/onboarding/OnboardingTour";
import { openCommandPalette } from "@/components/CommandPalette";

function StateDot() {
  const status = useDashboardStore((s) => s.status);
  const connected = useDashboardStore((s) => s.connected);
  const tone =
    !connected || !status
      ? "bg-muted"
      : status.state === "bonded"
        ? "bg-good"
        : status.state === "degraded"
          ? "bg-warn"
          : "bg-bad";
  const label = !status ? "—" : status.state.toUpperCase();
  return (
    <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted">
      <span className={cn("h-2 w-2 rounded-full", tone)} />
      <span>{label}</span>
    </div>
  );
}

function ThemeToggle() {
  // Start false on both server and the client's first render so hydration
  // matches; sync to the real (possibly inline-script-set) class after mount.
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("omr-theme", next ? "dark" : "light");
    } catch {
      /* ignore */
    }
  };
  return (
    <button
      onClick={toggle}
      className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-2"
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
      {dark ? "Hell" : "Dunkel"}
    </button>
  );
}

function RestartTourButton() {
  const router = useRouter();
  const start = () => {
    requestTour();
    router.push("/dashboard");
  };
  return (
    <button
      onClick={start}
      className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-2"
    >
      <Compass size={16} /> Tour starten
    </button>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Mobile top bar */}
      <div className="fixed top-0 left-0 right-0 z-30 flex items-center justify-between border-b border-border bg-surface px-4 py-3 md:hidden">
        <div className="flex items-center gap-2 font-semibold">
          <Network size={18} className="text-primary" /> OMR
        </div>
        <button onClick={() => setOpen(!open)} className="text-fg">
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-border bg-surface transition-transform md:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-2 px-4 py-4 text-lg font-bold">
          <Network className="text-primary" /> OMR Dashboard
        </div>
        <StateDot />
        <button
          onClick={openCommandPalette}
          className="mx-2 mb-1 flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-muted hover:bg-surface-2"
        >
          <Search size={14} /> Suche
          <kbd className="ml-auto rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px]">⌘K</kbd>
        </button>
        <nav className="mt-2 flex-1 space-y-0.5 overflow-y-auto px-2">
          {NAV.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                data-tour-step={item.tourId}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                  active
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted hover:bg-surface-2 hover:text-fg",
                )}
              >
                <Icon size={17} />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-2">
          <RestartTourButton />
          <ThemeToggle />
        </div>
      </aside>

      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/40 md:hidden"
          onClick={() => setOpen(false)}
        />
      )}
    </>
  );
}
