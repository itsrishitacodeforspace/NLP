/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Proxy /api -> backend so the browser only ever talks to same-origin in
    // development. The backend URL comes from BACKEND_URL (default :8010 here;
    // :8000 in the standard deployment — see README).
    const backend = process.env.BACKEND_URL || 'http://127.0.0.1:8010';
    return [
      {
        source: '/api/:path*',
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
