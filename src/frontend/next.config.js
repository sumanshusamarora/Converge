const { PHASE_DEVELOPMENT_SERVER } = require('next/constants')

/** @type {(phase: string) => import('next').NextConfig} */
module.exports = (phase) => ({
  output: 'standalone',
  // Keep dev and production artifacts separate to avoid stale chunk/runtime mismatches.
  distDir: phase === PHASE_DEVELOPMENT_SERVER ? '.next-dev' : '.next',
})
