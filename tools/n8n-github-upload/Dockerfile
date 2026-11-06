# Preparation only: build and runtime checks have NOT run in this Work.
FROM docker.n8n.io/n8nio/n8n:2.46.6
# Fail the build if this release image cannot support the intended Git route.
RUN git --version && node --version && mkdir -p /home/node/.n8n-files/git /home/node/.n8n-files/uploads
