# =============================================================================
# Stage 1: Build React + TypeScript + Vite SPA
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code and build production bundle
COPY . .
RUN npm run build

# =============================================================================
# Stage 2: Production Server with Nginx Alpine & Security Headers
# =============================================================================
FROM nginx:1.27-alpine AS production

# Remove default nginx config and apply custom SPA + CSP configuration
RUN rm -rf /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
