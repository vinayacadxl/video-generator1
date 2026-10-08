import type { NextConfig } from "next";

// Always static-export so FastAPI can serve frontend/out (and web/) without stale Blender UI.
const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  ...(!isDev ? { output: "export" } : {}),
  ...(isDev
    ? {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: "http://127.0.0.1:8000/api/:path*",
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
