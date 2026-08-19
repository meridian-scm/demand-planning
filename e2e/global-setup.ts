import { execSync } from "node:child_process";

/**
 * Resets and reseeds the demo database before the E2E suite runs, so every
 * run starts from the same deterministic state regardless of what earlier
 * manual testing left behind. Shells out to the backend container rather
 * than hitting a REST endpoint because seeding is a destructive, ops-style
 * action that intentionally has no public API surface.
 */
export default async function globalSetup(): Promise<void> {
  const skip = process.env.E2E_SKIP_SEED === "1";
  if (skip) {
    console.log("[global-setup] E2E_SKIP_SEED=1 — leaving the database as-is");
    return;
  }

  console.log("[global-setup] reseeding demo data via the backend container…");
  try {
    execSync("docker compose exec -T backend python -m app.seed.cli", {
      cwd: "..",
      stdio: "inherit",
    });
  } catch (error) {
    console.warn(
      "[global-setup] could not reseed via docker compose — assuming the stack is already " +
        "seeded or is being run outside Docker. Set E2E_SKIP_SEED=1 to silence this.",
      error,
    );
  }
}
