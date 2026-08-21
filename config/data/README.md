# Data configuration

- `test.yaml` is the fast deterministic development and CI profile. It retains exactly five stores
  while reducing the product and month counts.
- `reference.yaml` defines the approved 5 × 3,500 × 60 profile. Do not generate it during ordinary
  development or pull-request verification.

Both profiles pin the business period, generation timestamp, random seed, schema version, and output
directory. Changing scale or dates requires a new data version rather than source-code edits.
