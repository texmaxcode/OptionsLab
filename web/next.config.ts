import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: [
    "http://192.168.1.16:3000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
  ],
  /** Some deployments returned 404 for `documentation.html`; chapter lives at `docs.html` now. */
  async redirects() {
    return [
      {
        source: "/user-manual/documentation.html",
        destination: "/user-manual/docs.html",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
