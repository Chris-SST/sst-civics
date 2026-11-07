# Guide-site builder (D-073): builds the Astro site on the server whenever articles change and
# swaps the live release. See builder.mjs and docs/runbooks/articles.md.
# Docker Hub rate-limits the server: pull the base through the mirror and tag it first
#   docker pull mirror.gcr.io/library/node:22-alpine && docker tag mirror.gcr.io/library/node:22-alpine node:22-alpine
FROM node:22-alpine
WORKDIR /app/site
COPY --chown=node:node site/package.json site/package-lock.json ./
RUN npm ci --no-audit --no-fund && chown -R node:node /app
COPY --chown=node:node site/ ./
# The glossary page reads ../content/glossary at build time.
COPY --chown=node:node content/glossary /app/content/glossary
COPY --chown=node:node infra/sitebuilder/builder.mjs /app/builder.mjs
ARG SOURCE_REV=
ENV SOURCE_REV=$SOURCE_REV \
    ASTRO_TELEMETRY_DISABLED=1 \
    NODE_OPTIONS=--max-old-space-size=768
USER node
CMD ["node", "/app/builder.mjs"]
