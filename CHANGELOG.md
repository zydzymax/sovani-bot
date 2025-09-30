# Changelog

All notable changes to SoVAni Bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CHANGELOG.md to track all changes
- Feature branch `feature/hardening-and-refactor` for production hardening

### Changed
- Project structure refactoring in progress

### Fixed
- Critical data accuracy issues (see CRITICAL_AUDIT_REPORT.md)

### Security
- Security hardening and secrets management improvements in progress

---

## Previous Work (2025-09-30)

### Fixed
- Critical data duplication issues in API chunking (70-80% of data inflation)
- Date filtering using datetime objects instead of string comparison (10-15% of discrepancies)
- Unified forPay/priceWithDisc metrics for clear financial reporting (10-15% of distortions)

### Added
- Comprehensive validation test suite
- Data validation system with automatic alerting
- Critical audit report and fixes documentation

### Removed
- Legacy correction coefficients (archived in `archived_legacy_code/`)

---

**Note:** This changelog tracks changes from the hardening and refactoring initiative forward.
Previous work is summarized above for context.
