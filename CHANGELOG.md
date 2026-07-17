# Changelog

## Unreleased

## 0.3.1 - 2026-07-18

- Add top-level heart-rate and SpO2 analysis workflows backed by the public `analyze` API.
- Add visual/source editing, validation, filtering, and built-in templates for analysis rules.
- Upgrade and pin the public API dependency to ghealth-tools 0.5.1.
- Remove duplicate wheel inclusion rules so release packages build successfully.

## 0.3.0 - 2026-07-17

- Upgrade and pin the public API dependency to ghealth-tools 0.4.58.
- Split the rule library and global configuration into independent pages and view models.
- Stop scalar rule edits and catalog refreshes from resetting the key tree; remap selection after
  list insert, move, and removal operations.
- Add guided Parse, Convert, Chip, Classify, and Evaluate rule generation with immutable sample
  analysis, warning confirmation, public validation/save, and cancellable temporary previews.
- Detect HR, HRV, ADT, and ADTdata groups in the supplied LOG while excluding truncated or
  interleaved lines from generated patterns.
- Add CSV profiling, API-initialized conversion mapping, ordered chip column groups, common column
  templates, custom ranges, roles, and target zero-fill warnings.
- Add Offline directory states and rescanning, five Check choices, all seven Plot types, conditional
  Plot fields, and corrected PSD RMS handling.
- Version Windows artifacts as `health-tools-ui-0.3.0-windows-x64.zip` and
  `health-tools-ui-setup-0.3.0.exe`.

- Repair empty offline version selectors by scanning an empty catalog during startup.
- Explain invalid or unscanned offline directories instead of showing a silent disabled control.
- Refresh chip and version choices immediately after changing the offline tools directory.
- Upgrade the public API dependency to ghealth-tools 0.4.57 for stable path migration.

## 0.2.0 - 2026-07-17

- Migrate all 13 operations to the typed `health_tools.api` contract from ghealth-tools 0.4.56.
- Add QThread execution for regular operations and isolated NDJSON execution for offline jobs.
- Add structured progress, cooperative cancellation, partial results, public error handling, and persisted result history.
- Migrate rule, configuration, validation, and offline catalog services away from internal upstream modules.
- Add HuskarUI progress and structured result views, including per-file status tables.
- Update Windows packaging and CI smoke tests for the public API worker protocol.

## 0.1.1 - 2026-07-16

- Upgrade the bundled ghealth-tools runtime from 0.4.49 to 0.4.53.
- Add the latest offline PPG mapping and output settle timeout options.

## 0.1.0 - 2026-07-16

- Initial PyHuskarUI desktop application.
- Complete ghealth-tools command catalog and queued execution.
- Visual and source YAML rule editing.
- Windows portable and installer build definitions.
