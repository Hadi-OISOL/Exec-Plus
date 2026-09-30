# Use case: Packages the ExecPlus web application for container deployment.
# What it does: Builds and runs the standalone Next.js server as a non-root user.

ARG NODE_IMAGE=node:22-alpine
FROM ${NODE_IMAGE} AS dependencies

WORKDIR /app

COPY package.json package-lock.json* ./
COPY apps/web/package.json ./apps/web/package.json

RUN npm ci

FROM ${NODE_IMAGE} AS builder

WORKDIR /app

COPY --from=dependencies /app/node_modules ./node_modules
COPY package.json ./
COPY apps/web ./apps/web

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build:web

FROM ${NODE_IMAGE} AS runtime

ENV NODE_ENV=production

WORKDIR /app

RUN addgroup --system --gid 1001 execplus
RUN adduser --system --uid 1001 execplus

COPY --from=builder --chown=execplus:execplus /app/apps/web/.next/standalone ./
COPY --from=builder --chown=execplus:execplus /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder --chown=execplus:execplus /app/apps/web/public ./apps/web/public

USER execplus

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
