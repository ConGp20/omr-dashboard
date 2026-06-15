"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Network } from "lucide-react";

/**
 * Entry point. First run (no completed-setup flag) routes to the wizard,
 * otherwise to the live dashboard.
 */
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    let configured = false;
    try {
      configured = localStorage.getItem("omr-configured") === "true";
    } catch {
      /* ignore */
    }
    router.replace(configured ? "/dashboard" : "/wizard");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Network size={32} className="animate-pulse text-primary" />
    </div>
  );
}
