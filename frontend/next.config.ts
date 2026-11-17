import type { NextConfig } from "next";

const BACKEND_INTERNAL_URL =
  process.env.INTERNAL_BACKEND_URL || "http://127.0.0.1:8000/api/v1";

const nextConfig: NextConfig = {
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${BACKEND_INTERNAL_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
