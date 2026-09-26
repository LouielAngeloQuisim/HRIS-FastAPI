# Stage 0: build the frontendv3 app
FROM node:26-alpine AS build-stage

WORKDIR /app

COPY frontendv3/package.json ./
COPY frontendv3/pnpm-lock.yaml ./
COPY frontendv3/pnpm-workspace.yaml ./
COPY frontendv3/.npmrc ./

RUN corepack enable && corepack prepare pnpm@11.17.0 --activate

RUN pnpm install --frozen-lockfile

COPY frontendv3/ ./

ARG VITE_API_URL
ARG NODE_ENV=production

RUN pnpm build

# Stage 1: serve with nginx
FROM nginx:1

COPY --from=build-stage /app/dist/ /usr/share/nginx/html

COPY frontendv3/nginx.conf /etc/nginx/conf.d/default.conf
COPY frontendv3/nginx-backend-not-found.conf /etc/nginx/extra-conf.d/backend-not-found.conf
