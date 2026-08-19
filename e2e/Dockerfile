# Lets the E2E suite run without installing Node/Playwright browsers on the
# host at all — useful on machines (like the one this project was built on)
# that have Docker but not Node. See docs/TESTING.md for usage.
FROM mcr.microsoft.com/playwright:v1.62.1-jammy

WORKDIR /e2e

COPY package.json ./
RUN npm install

COPY . .

CMD ["npx", "playwright", "test"]
