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
  Cable,
  Bell,
  Gauge,
  HeartPulse,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Matches a data-tour-step id used by the onboarding tour, if any. */
  tourId?: string;
}

export const NAV: NavItem[] = [
  { href: "/dashboard", label: "Übersicht", icon: Activity, tourId: "nav-dashboard" },
  { href: "/links", label: "Verbindungen", icon: Cable, tourId: "nav-links" },
  { href: "/protocols", label: "Protokoll", icon: Network },
  { href: "/vps", label: "VPS-Endpunkt", icon: Server, tourId: "nav-vps" },
  { href: "/firewall", label: "Firewall & Ports", icon: Shield },
  { href: "/qos", label: "QoS & Traffic", icon: Sliders },
  { href: "/dns", label: "DNS", icon: Globe },
  { href: "/monitoring", label: "Verlauf", icon: LineChart },
  { href: "/usage", label: "Datenverbrauch", icon: Gauge },
  { href: "/alerts", label: "Alarme", icon: Bell },
  { href: "/diagnostics", label: "Diagnose", icon: Stethoscope },
  { href: "/health", label: "Systemcheck", icon: HeartPulse },
  { href: "/config-map", label: "Konfig-Karte", icon: Map, tourId: "nav-config-map" },
  { href: "/system", label: "System", icon: Settings },
];
