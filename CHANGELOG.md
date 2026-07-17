# Changelog

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
