/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  experimental: {
    serverComponentsExternalPackages: [],
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'data-talent-v2.basecdn.net',
        pathname: '/careerportalvinuni/**',
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: '/v1/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
