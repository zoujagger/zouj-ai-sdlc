<!-- Example "Project notes" for CLAUDE.md, Go stack (bootstrap --stack go). Copy, then edit to match your project. -->
## Project notes
- **Stack:** Go 1.23, chi router, pgx + sqlc for PostgreSQL, standard library `testing` + `testify/require`.
- **Layout:** `cmd/server/` (main), `internal/<domain>/` (handlers, service, store per domain), `db/queries/` (sqlc input), `db/migrations/`.
- **Commands:** `make check` = `go vet ./...` + `go build ./...` + `go test ./...`. Race check: `go test -race ./...` (runs in CI).
- **Conventions:** errors wrapped with `fmt.Errorf("...: %w", err)`; context passed first; no package-level state outside `cmd/`.
- **Gotchas:** after editing `db/queries/*.sql` run `sqlc generate` and commit the output; table tests for every handler.
