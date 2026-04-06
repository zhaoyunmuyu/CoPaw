## 1. Remove provider initialization from tenant middleware

- [x] 1.1 Identify the provider storage initialization call sites inside `TenantWorkspaceMiddleware`
- [x] 1.2 Remove provider storage initialization responsibility from tenant middleware while preserving workspace bootstrap and tenant model binding
- [x] 1.3 Ensure middleware behavior for non-provider tenant requests no longer materializes tenant provider storage

## 2. Add provider feature entrypoint readiness checks

- [x] 2.1 Add tenant provider storage readiness checks to provider management API entrypoints
- [x] 2.2 Add tenant provider storage readiness checks to local model API entrypoints
- [x] 2.3 Add tenant provider storage readiness checks to runtime model creation paths in `model_factory`
- [x] 2.4 Keep readiness logic idempotent and concurrency-safe for first-use initialization

## 3. Verify behavior and prevent regressions

- [x] 3.1 Add or update tests to verify non-provider tenant requests do not initialize provider storage
- [x] 3.2 Add or update tests to verify first provider API use initializes tenant provider storage correctly
- [x] 3.3 Add or update tests to verify first runtime model creation initializes tenant provider storage correctly
- [x] 3.4 Validate that tenant isolation and existing provider storage semantics remain unchanged
