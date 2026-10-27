<!-- Example "Project notes" for CLAUDE.md, Node/TypeScript stack (bootstrap --stack node). Copy, then edit to match your project. -->
## Project notes
- **Stack:** TypeScript 5 (strict), Node 22, Next.js 15 (App Router), Prisma + PostgreSQL, Vitest, Playwright for e2e. Package manager: `npm`.
- **Layout:** `app/` (routes and UI), `lib/` (domain logic, no React imports), `prisma/` (schema, migrations), `e2e/` (Playwright).
- **Commands:** `make check` = `npm run lint` + `npx tsc --noEmit` + `npm test`. E2E: `npx playwright test` (not in `make check`, runs in CI).
- **Conventions:** server code in `lib/` is pure and unit-tested; validate all input with `zod` at the route boundary; no `any`.
- **Gotchas:** `prisma generate` runs on `postinstall`; after a schema change run `npx prisma migrate dev`. Never edit `package-lock.json` by hand.
