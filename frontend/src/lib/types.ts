// TypeScript mirror of the backend Pydantic schemas (see backend/schemas.py).

export type BondState = "bonded" | "degraded" | "offline";
export type LinkState = "up" | "degraded" | "down" | "disabled";
export type LinkType =
  | "fiber"
  | "dsl"
  | "lte"
  | "5g"
  | "ethernet"
  | "satellite"
  | "other";
export type ConfigOwner = "router" | "vps" | "sync";

export interface LinkStatus {
  id: string;
  label: string;
  type: LinkType;
  state: LinkState;
  enabled: boolean;
  priority: number;
  ip?: string | null;
  rx_bps: number;
  tx_bps: number;
  latency_ms?: number | null;
  packet_loss_pct?: number | null;
  multipath: string;
}

export interface TunnelStatus {
  protocol: string;
  up: boolean;
  encryption?: string | null;
  rx_bps: number;
  tx_bps: number;
  local_ip?: string | null;
  remote_ip?: string | null;
}

export interface DashboardStatus {
  configured: boolean;
  state: BondState;
  links: LinkStatus[];
  tunnel?: TunnelStatus | null;
  total_rx_bps: number;
  total_tx_bps: number;
  active_links: number;
  total_links: number;
  vps_public_ip?: string | null;
  exit_vpn?: string | null;
  timestamp: number;
}

export interface TopoNode {
  id: string;
  type: string;
  label: string;
  state: string;
  owner?: ConfigOwner | null;
  detail: Record<string, unknown>;
}

export interface TopoEdge {
  id: string;
  source: string;
  target: string;
  animated: boolean;
  label?: string | null;
  bps: number;
}

export interface Topology {
  nodes: TopoNode[];
  edges: TopoEdge[];
}

export interface ProtocolInfo {
  id: string;
  name: string;
  active: boolean;
  available: boolean;
  good_for: string;
  avoid_when: string;
  technical: string;
  vps_port?: number | null;
  recommended: boolean;
}

export interface IngressTarget {
  dest_ip: string;
  dest_port: number;
  weight: number;
}

export interface PortForward {
  id?: string | null;
  description: string;
  proto: "tcp" | "udp" | "tcp/udp";
  src_port: number;
  src_port_end?: number | null;
  dest_ip: string;
  dest_port: number;
  enabled: boolean;
  extra_targets: IngressTarget[];
  allow_src_cidrs: string[];
  deny_src_cidrs: string[];
  rate_limit_per_min?: number | null;
}

export interface ExitVpn {
  enabled: boolean;
  type: "wireguard" | "openvpn" | "none";
  endpoint?: string | null;
  public_key?: string | null;
  private_key?: string | null;
  allowed_ips: string;
  kill_switch: boolean;
}

export interface NatStatus {
  masquerade: boolean;
  public_ipv4?: string | null;
  public_ipv6?: string | null;
  tunnel_clients: string[];
}

export interface TopologyHost {
  ip: string;
  label: string;
  source: string;
}

export interface FirewallRule {
  id?: string | null;
  action: "allow" | "block";
  src_zone: string;
  dest_zone: string;
  proto: "tcp" | "udp" | "tcp/udp";
  port: string;
  description: string;
  enabled: boolean;
}

export interface DomainRule {
  id?: string | null;
  domain: string;
  target: string;
}

export interface DnsConfig {
  upstream: string[];
  mode: "classic" | "doh" | "dot";
  local_entries: { hostname: string; ip: string }[];
}

export interface MetricPoint {
  ts: number;
  link_id: string;
  rx_bps: number;
  tx_bps: number;
  latency_ms?: number | null;
  packet_loss_pct?: number | null;
}

export interface AppEvent {
  ts: number;
  type: string;
  detail: string;
  severity: "info" | "warn" | "error";
}

export interface ComponentVersion {
  component: string;
  installed: string;
  available?: string | null;
  update_available: boolean;
  changelog_url?: string | null;
}

export interface WizardWan {
  id: string;
  interface: string;
  detected_type: LinkType;
  label: string;
  ip?: string | null;
  up: boolean;
  enabled: boolean;
}

export interface ConnectionSettings {
  router_ip: string;
  router_user: string;
  router_pass_set: boolean;
  omr_admin_key_set: boolean;
  overridden: string[];
}

export interface ConnectionTestResult {
  router_reachable: boolean;
  router_detail: string;
  omr_admin_reachable: boolean;
  omr_admin_detail: string;
}

export interface SecuritySettings {
  dashboard_user: string;
  dashboard_pass_set: boolean;
  jwt_secret_set: boolean;
  overridden: string[];
}

export interface ConfigMapItem {
  key: string;
  label: string;
  page?: string;
  description: string;
}
export interface ConfigMap {
  router: ConfigMapItem[];
  vps: ConfigMapItem[];
  sync: ConfigMapItem[];
}

export interface LinkUsage {
  link_id: string;
  label: string;
  rx_bytes: number;
  tx_bytes: number;
  total_bytes: number;
  cap_gb?: number | null;
  warn_pct: number;
  used_pct?: number | null;
  over_warn: boolean;
  over_cap: boolean;
  projected_bytes: number;
  projected_pct?: number | null;
  projected_over_cap: boolean;
}

export interface UsageResponse {
  month: string;
  total_bytes: number;
  links: LinkUsage[];
  day_of_month: number;
  days_in_month: number;
}

export interface AlertConfigPublic {
  min_severity: "warn" | "error";
  cooldown_minutes: number;
  telegram_enabled: boolean;
  telegram_chat_id?: string | null;
  telegram_token_set: boolean;
  webhook_enabled: boolean;
  webhook_url?: string | null;
  email_enabled: boolean;
  smtp_host?: string | null;
  smtp_port: number;
  smtp_user?: string | null;
  smtp_pass_set: boolean;
  smtp_tls: boolean;
  email_from?: string | null;
  email_to?: string | null;
}

export interface AlertTestResult {
  results: Record<string, string>;
}

export interface AuthStatus {
  auth_required: boolean;
  demo: boolean;
  username: string;
}

export interface Finding {
  id: string;
  severity: "error" | "warn" | "info";
  title: string;
  detail: string;
  action: string;
  page?: string | null;
  category: string;
}

export interface HealthReport {
  findings: Finding[];
  errors: number;
  warnings: number;
  infos: number;
  checked: number;
}

export interface RoutingOverview {
  default_exit: string;
  exit_vpn_enabled: boolean;
  routes: { destination: string; via: string }[];
}
