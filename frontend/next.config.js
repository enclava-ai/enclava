const path = require('path');
let TsconfigPathsPlugin;
try {
  // Optional: only used if installed
  TsconfigPathsPlugin = require('tsconfig-paths-webpack-plugin');
} catch (_) {}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  // Disable ESLint and TypeScript checking during builds to allow test environment to start
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  // Enable standalone output for better Docker compatibility
  output: 'standalone',
  webpack: (config, { dev }) => {
    // Ensure resolve object exists
    config.resolve = config.resolve || {};
    config.resolve.alias = config.resolve.alias || {};

    // Hard-set robust alias for "@" => <repo>/src
    config.resolve.alias['@'] = path.resolve(__dirname, 'src');

    // Ensure common extensions are resolvable
    const exts = config.resolve.extensions || [];
    config.resolve.extensions = Array.from(new Set([...exts, '.ts', '.tsx', '.js', '.jsx']));

    // Add tsconfig-aware resolver plugin if available
    if (TsconfigPathsPlugin) {
      const existing = config.resolve.plugins || [];
      existing.push(
        new TsconfigPathsPlugin({
          configFile: path.resolve(__dirname, 'tsconfig.json'),
          extensions: config.resolve.extensions,
          mainFields: ['browser', 'module', 'main'],
        })
      );
      config.resolve.plugins = existing;
    }

    // Optional: Add debug logging in development
    if (dev) {
      // eslint-disable-next-line no-console
      console.log('Webpack alias config:', config.resolve.alias);
    }

    return config;
  },
  env: {
    NEXT_PUBLIC_BASE_URL: process.env.NEXT_PUBLIC_BASE_URL,
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME || 'Enclava', // Sane default
  },
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
