"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Activity,
  Network,
  Server,
  Sliders,
  Globe,
  Shield,
  LineChart,
  Stethoscope,
  Map,
  Settings,
  Moon,
  Sun,
  Menu,
  X,
  Cable,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useDashboardStore } from "@/lib/store";

const NAV = [
  { href: "/dashboard", label: "Übersicht", icon: Activity },
  { href: "/links", label: "Verbindungen", icon: Cable },
  { href: "/protocols", label: "Protokoll", icon: Network },
  { href: "/vps", label: "VPS-Endpunkt", icon: Server },
  { href: "/firewall", label: "Firewall & Ports", icon: Shield },
  { href: "/qos", label: "QoS & Traffic", icon: Sliders },
  { href: "/dns", label: "DNS", icon: Globe },
  { href: "/monitoring", label: "Verlauf", icon: LineChart },
  { href: "/diagnostics", label: "Diagnose", icon: Stethoscope },
  { href: "/config-map", label: "Konfig-Karte", icon: Map },
  { href: "/system", label: "System", icon: Settings },
];

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
  const [dark, setDark] = useState(
    typeof document !== "undefined" && document.documentElement.classList.contains("dark"),
  );
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
        <nav className="mt-2 flex-1 space-y-0.5 overflow-y-auto px-2">
          {NAV.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
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
