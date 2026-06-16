# Build context is the REPO ROOT (see infra/docker-compose.yml web.build.context: ..)
# so the pnpm workspace + packages/shared-types are available.
FROM node:22-bookworm-slim

RUN corepack enable
WORKDIR /app

# Workspace manifests first (better layer caching).
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY packages ./packages
COPY apps/web ./apps/web

RUN pnpm install --frozen-lockfile
RUN pnpm --filter web build

EXPOSE 3000
WORKDIR /app/apps/web
# next start binds 0.0.0.0:3000 by default.
CMD ["pnpm", "start"]
