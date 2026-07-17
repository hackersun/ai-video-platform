# Task 9 Report — Versioned Anime Production Recipes

## Scope delivered

- Added pure `ProductionRecipeSpec` validation for the mutually exclusive
  `video_native_audio` and `separate_tts` routes.
- Enforced video native-audio support, TTS exclusion/requirement, subtitle source,
  render, storage, required stage bindings, and deterministic error codes.
- Validated every referenced binding against its stage task/capability, published
  profile, active binding, enabled model/provider, verified connection, provider
  match, and tenant or trusted-system ownership.
- Added deterministic SHA-256 checksums plus draft create/update, publish, and
  append-only next-version application services.
- Kept ORM reads in `model_config/repository.py`; `recipes.py` remains pure and has
  no SQLAlchemy, model, or repository dependency.
- Preserved the existing model-center ORM/SQL published-version guards and locked
  them with Task 9 tests.
- Exported the Task 9 contract only through `model_config/public.py`.

## TDD evidence

1. RED: `tests/test_production_recipe_contract.py` failed during collection because
   `RecipeBindingContract` and the recipe public API did not exist.
2. GREEN: the new recipe suite reached `15 passed`, then an additional plan-shaped
   native-capability test was observed failing before the minimal compatibility
   behavior was added.
3. REFACTOR: split persistence orchestration into `recipe_versions.py`; final new
   production files are 226 and 134 lines, with no function over 80 lines.

## Fresh verification

All commands used a fresh `/tmp/*.db`, `E2E_REQUIRE_ISOLATED_DB=true`, development
mode, and a transient test-only Fernet key.

- Task 9 recipe suite: `16 passed`.
- Task 9 recipe + legacy workflow-media contract: `31 passed`.
- Expanded Task 9 gate covering binding, strategy, domain, repository, schema,
  migration, version guards, security, and workflow media: `151 passed in 11.74s`.
- `compileall`: passed for the changed model-config package and recipe test.
- `git diff --check`: passed.
- AST/line guard: passed; production functions <= 80 lines, tests <= 150 lines,
  new production files <= 300 lines, touched production files <= 500 lines.
- Query ownership scan: no `select`, `db.get`, `db.scalar`, or `db.execute` in
  `recipes.py` or `recipe_versions.py`; pure `recipes.py` imports no ORM/model/repository.

## Boundaries and review

- No Task 10 production caller cutover.
- No Prompt Profile, snapshot, API route, frontend, migration-schema, live DB,
  network, provider SDK, or paid-call changes.
- No workflow-media production file changed; its full public contract passed.
- Inline review found no critical or important issue. The stage task names are
  intentionally centralized in `STAGE_REQUIREMENTS`; Task 10 should consume these
  exact task semantics rather than introduce a second mapping.
