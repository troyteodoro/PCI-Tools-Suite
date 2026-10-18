# syntax=docker/dockerfile:1.7
#
# Production web image: Vite build served by nginx. Local development runs the Vite dev
# server instead (see compose.override.yml), so this path is only exercised by prod builds.

FROM node:26-alpine AS build

WORKDIR /app

# No `*` on the lockfile and no `|| npm install` fallback: both would let the image build
# succeed with dependencies that do not match the lock, which is the one thing `npm ci`
# exists to prevent. A missing or stale lockfile should fail here, loudly.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src

RUN npm run build

FROM nginx:1.27-alpine AS runtime

RUN rm /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/demarc.conf

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
