import { cn } from "@/lib/utils";

const OWNERS = {
  router: { label: "🖥️ Router", cls: "bg-blue-500/15 text-blue-500 dark:text-blue-400" },
  vps: { label: "☁️ VPS", cls: "bg-purple-500/15 text-purple-500 dark:text-purple-400" },
  sync: { label: "🔄 Auto-Sync", cls: "bg-amber-500/15 text-amber-600 dark:text-amber-400" },
};

/** Shows where a setting lives: on the router, on the VPS, or auto-synced. */
export function OwnerBadge({
  owner,
  className,
}: {
  owner: keyof typeof OWNERS;
  className?: string;
}) {
  const o = OWNERS[owner];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium",
        o.cls,
        className,
      )}
    >
      {o.label}
    </span>
  );
}
