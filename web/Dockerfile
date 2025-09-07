# Multi-stage Dockerfile for Pulse Web - Staff Engineer Setup
# Optimized for Next.js with proper caching

# Base stage
FROM node:20-alpine as base

# Install system dependencies
RUN apk add --no-cache libc6-compat curl

# Set working directory
WORKDIR /app

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Dependencies stage
FROM base as deps

# Copy package files
COPY package*.json ./

# Install dependencies
RUN \
  if [ -f yarn.lock ]; then yarn --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm ci; \
  else echo "No lockfile found" && exit 1; \
  fi

# Development stage
FROM base as development

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY . .

# Set ownership
RUN chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Set environment
ENV NODE_ENV=development

# Development command with hot reload
CMD ["npm", "run", "dev"]

# Builder stage
FROM base as builder

# Copy dependencies
COPY --from=deps /app/node_modules ./node_modules

# Copy source code
COPY . .

# Set environment for build
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# Build application
RUN \
  if [ -f yarn.lock ]; then yarn build; \
  else npm run build; \
  fi

# Production stage
FROM base as production

# Set environment
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Copy built application
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000 || exit 1

# Production command
CMD ["node", "server.js"]

# Testing stage
FROM development as testing

# Install additional test dependencies
RUN npm install --only=dev

# Run tests
RUN npm test

# Linting stage
FROM development as linting

# Run linting
RUN npm run lint