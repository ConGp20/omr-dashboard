"use client";
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useRouter, usePathname } from "next/navigation";
import { ArrowRight, X } from "lucide-react";
import { Button } from "@/components/ui/primitives";

/** localStorage flag, used to hand the tour off across a full page navigation
 * (e.g. wizard -> dashboard, where this component isn't mounted yet to hear
 * the start event below). */
export const TOUR_STORAGE_KEY = "omr-tour-active";

const START_EVENT = "omr:start-tour";

/** Start the tour from anywhere. Works whether OnboardingTour is already
 * mounted (dispatches an event it's listening for) or about to mount after
 * a navigation (the localStorage flag is picked up on mount). */
export function requestTour() {
  try {
    localStorage.setItem(TOUR_STORAGE_KEY, "true");
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event(START_EVENT));
}

interface Step {
  target: string; // matches a data-tour-step attribute
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    target: "status-banner",
    title: "Gesamtstatus",
    body: "BONDED / DEGRADED / OFFLINE auf einen Blick — plus die aktuelle Gesamtbandbreite über alle Leitungen.",
  },
  {
    target: "link-cards",
    title: "Deine Leitungen",
    body: "Jede WAN-Verbindung mit Live-Durchsatz, Latenz und Paketverlust. Klicke auf „Verbindungen“ in der Navigation, um sie umzubenennen oder zu priorisieren.",
  },
  {
    target: "topology",
    title: "Netzwerk-Topologie",
    body: "Zeigt den kompletten Pfad vom Router über den Tunnel bis zum VPS. Klicke auf einen Knoten, um direkt zur passenden Einstellung zu springen.",
  },
  {
    target: "nav-links",
    title: "Verbindungen verwalten",
    body: "Leitungen benennen, priorisieren oder vorübergehend deaktivieren — ohne sie zu löschen.",
  },
  {
    target: "nav-vps",
    title: "VPS-Endpunkt",
    body: "Port-Weiterleitungen, Exit-VPN und NAT-Status — alles, was auf dem Server zusammenläuft.",
  },
  {
    target: "nav-config-map",
    title: "Konfig-Karte",
    body: "Zeigt auf einen Blick, ob eine Einstellung auf dem Router, dem VPS oder automatisch synchronisiert wird.",
  },
];

const PAD = 8;
const CARD_WIDTH = 320;

export function OnboardingTour() {
  const pathname = usePathname();
  const router = useRouter();
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    let shouldStart = false;
    try {
      shouldStart = localStorage.getItem(TOUR_STORAGE_KEY) === "true";
    } catch {
      /* ignore */
    }
    if (shouldStart) {
      setActive(true);
      setStepIndex(0);
    }

    const onStart = () => {
      setActive(true);
      setStepIndex(0);
    };
    window.addEventListener(START_EVENT, onStart);
    return () => window.removeEventListener(START_EVENT, onStart);
  }, []);

  useEffect(() => {
    if (active && pathname !== "/dashboard") router.push("/dashboard");
  }, [active, pathname, router]);

  const measure = useCallback(() => {
    if (!active) return;
    const el = document.querySelector(`[data-tour-step="${STEPS[stepIndex].target}"]`);
    if (!el) {
      setRect(null);
      return;
    }
    const r = el.getBoundingClientRect();
    const visible =
      r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0 &&
      r.left < window.innerWidth && r.top < window.innerHeight;
    setRect(visible ? r : null);
  }, [active, stepIndex]);

  useEffect(() => {
    measure();
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    // Targets can mount slightly after a route change (data fetch); poll briefly.
    const poll = setInterval(measure, 300);
    return () => {
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
      clearInterval(poll);
    };
  }, [measure]);

  const finish = () => {
    setActive(false);
    try {
      localStorage.removeItem(TOUR_STORAGE_KEY);
    } catch {
      /* ignore */
    }
  };
  const next = () => (stepIndex + 1 >= STEPS.length ? finish() : setStepIndex((i) => i + 1));
  const prev = () => setStepIndex((i) => Math.max(0, i - 1));

  if (!active) return null;
  const step = STEPS[stepIndex];
  const hasTarget = rect !== null;

  let cardStyle: CSSProperties = { position: "fixed", zIndex: 50, width: CARD_WIDTH };
  if (hasTarget && rect) {
    const fitsBelow = rect.bottom + PAD * 2 + 160 < window.innerHeight;
    const top = fitsBelow ? rect.bottom + PAD * 2 : Math.max(16, rect.top - PAD * 2 - 160);
    const left = Math.min(Math.max(16, rect.left), window.innerWidth - CARD_WIDTH - 16);
    cardStyle = { ...cardStyle, top, left };
  } else {
    cardStyle = { ...cardStyle, top: "40vh", left: "50%", transform: "translateX(-50%)" };
  }

  return (
    <>
      {hasTarget && rect ? (
        <>
          <div className="fixed left-0 right-0 top-0 z-40 bg-black/60" style={{ height: Math.max(0, rect.top - PAD) }} />
          <div className="fixed left-0 right-0 z-40 bg-black/60" style={{ top: rect.bottom + PAD, bottom: 0 }} />
          <div
            className="fixed z-40 bg-black/60"
            style={{ top: rect.top - PAD, height: rect.height + PAD * 2, left: 0, width: Math.max(0, rect.left - PAD) }}
          />
          <div
            className="fixed z-40 bg-black/60"
            style={{ top: rect.top - PAD, height: rect.height + PAD * 2, left: rect.right + PAD, right: 0 }}
          />
          <div
            className="pointer-events-none fixed z-40 rounded-lg ring-2 ring-primary"
            style={{ top: rect.top - PAD, left: rect.left - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 }}
          />
        </>
      ) : (
        <div className="fixed inset-0 z-40 bg-black/60" />
      )}

      <div style={cardStyle} className="rounded-xl border border-border bg-surface p-4 shadow-xl">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-muted">
            Schritt {stepIndex + 1} / {STEPS.length}
          </span>
          <button onClick={finish} className="text-muted hover:text-fg" aria-label="Tour beenden">
            <X size={15} />
          </button>
        </div>
        <h3 className="mb-1 text-sm font-semibold text-fg">{step.title}</h3>
        <p className="mb-3 text-sm text-muted">{step.body}</p>
        <div className="flex items-center justify-between">
          <button
            onClick={prev}
            disabled={stepIndex === 0}
            className="text-xs text-muted hover:text-fg disabled:opacity-40"
          >
            Zurück
          </button>
          <Button size="sm" onClick={next}>
            {stepIndex + 1 >= STEPS.length ? "Fertig" : <>Weiter <ArrowRight size={14} /></>}
          </Button>
        </div>
      </div>
    </>
  );
}
