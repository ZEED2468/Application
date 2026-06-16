import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // shared-types is a source-only workspace package; let Next transpile it
  transpilePackages: ["@jd/shared-types"],
};

export default nextConfig;
