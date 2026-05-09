import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Monorepo: build may be triggered from repo root; trace files from workspace root.
  experimental: {
    outputFileTracingRoot: path.join(__dirname, "../.."),
  },
};

export default nextConfig;
