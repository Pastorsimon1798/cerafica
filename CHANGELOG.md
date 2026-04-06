# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Security
- Replaced eval() with sandboxed vm execution in regenerate_worldbuilding.mjs
- Restricted CORS to known domains on checkout function
- Added security headers (CSP, HSTS, XSS protection)
- Added rate limiting on checkout function
- Added authentication to feedback server
- Added input sanitization for idea seeds
- Fixed duplicate one-of-one cart validation
- Added max quantity/cart limits

### Architecture
- Consolidated duplicate products.json via symlink
- Extracted shared deployment utilities to shared/deploy-lib.sh
- Fixed git submodule URL

### Bug Fixes
- Fixed silent exception handlers in photo_export.py and instagram_scheduler.py
- Fixed race condition in photo ID generation
- Removed CI test failure masking

## [0.1.0] - 2026-04-05
- Initial release
