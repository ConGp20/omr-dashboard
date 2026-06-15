/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // The browser only ever talks to this Next.js server; it proxies to the
  // backend sidecar server-side (see src/app/api/**). BACKEND_URL is read at
  // runtime so the same image works in demo and production.
  env: {
    BACKEND_URL: process.env.BACKEND_URL || "http://127.0.0.1:8000",
  },
};

export default nextConfig;
