FROM node:26.10.0@sha256:9965105b7a4e201d7f07268402bb4971670592b46c9b9058cc643961199a1ab6
WORKDIR /app
COPY package.json yarn.lock ./
RUN npm install --global yarn@1.22.22 && yarn install --frozen-lockfile --non-interactive && yarn cache clean
COPY . .
ARG VITE_API_BASE_URL
ARG VITE_AUTH_EMAIL_ALLOWLIST
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_AUTH_EMAIL_ALLOWLIST=$VITE_AUTH_EMAIL_ALLOWLIST
RUN yarn build
