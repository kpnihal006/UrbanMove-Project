import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    domains: ["lh3.googleusercontent.com"],
  },
  env: {
    NEXT_PUBLIC_USER_SERVICE_URL: process.env.NEXT_PUBLIC_USER_SERVICE_URL ?? "",
    NEXT_PUBLIC_ROUTING_ENGINE_URL: process.env.NEXT_PUBLIC_ROUTING_ENGINE_URL ?? "",
    NEXT_PUBLIC_ANALYTICS_SERVICE_URL: process.env.NEXT_PUBLIC_ANALYTICS_SERVICE_URL ?? "",
  },
};

export default nextConfig;
