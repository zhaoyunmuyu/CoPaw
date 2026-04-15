## 1. Backend - Data Models and Configuration

- [x] 1.1 Create `src/swe/config/cases.py` - Pydantic models (Case, CaseDetail, CaseStep, CasesConfig, UserCasesConfig)
- [x] 1.2 Create `WORKING_DIR/cases.json` - Default case definitions with iframe_url and steps
- [x] 1.3 Create `WORKING_DIR/user_cases.json` - Default user-case mapping with `default` array

## 2. Backend - API Router

- [x] 2.1 Create `src/swe/app/routers/cases.py` - API router with endpoints
- [x] 2.2 Implement `GET /cases` - User-filtered case list (read X-User-Id header, fallback to default)
- [x] 2.3 Implement `GET /cases/{case_id}` - Case detail with iframe_url and steps
- [x] 2.4 Implement `POST /cases` - Create case (admin)
- [x] 2.5 Implement `PUT /cases/{case_id}` - Update case (admin)
- [x] 2.6 Implement `DELETE /cases/{case_id}` - Delete case (admin)
- [x] 2.7 Implement `GET /cases/admin/all` - List all cases (admin)
- [x] 2.8 Implement `GET /cases/admin/user-mapping` - Get user-case mapping (admin)
- [x] 2.9 Implement `PUT /cases/admin/user-mapping` - Update user-case mapping (admin)
- [x] 2.10 Register cases router in `src/swe/app/routers/__init__.py`

## 3. Frontend - API Module

- [x] 3.1 Create `console/src/api/types/cases.ts` - TypeScript types (Case, CaseDetail, CaseStep)
- [x] 3.2 Create `console/src/api/modules/cases.ts` - API functions (listCases, getCaseDetail, createCase, updateCase, deleteCase)
- [x] 3.3 Export types in `console/src/api/types/index.ts`

## 4. Frontend - FeaturedCases Component Update

- [x] 4.1 Remove DEFAULT_CASES hardcoding from `FeaturedCases/index.tsx`
- [x] 4.2 Add useEffect to call `GET /cases` on mount
- [x] 4.3 Add loading state while fetching cases
- [x] 4.4 Pass userId via X-User-Id header (use authHeaders or iframeStore)

## 5. Frontend - WelcomeCenterLayout Component Update

- [x] 5.1 Update `handleViewCase` to call `GET /cases/{case_id}` for detail
- [x] 5.2 Add loading state for case detail fetch
- [x] 5.3 Update `CaseDetailData` interface to include iframe_url and iframe_title
- [x] 5.4 Handle error when case not found

## 6. Frontend - CaseDetailDrawer Component Update

- [x] 6.1 Update layout to left-right split (steps left, iframe right)
- [x] 6.2 Remove hardcoded tableHeaders, tableRows, steps from component
- [x] 6.3 Render iframe with `src={iframe_url}` in right panel
- [x] 6.4 Add iframe_title as panel header
- [x] 6.5 Add sandbox attribute `allow-scripts allow-same-origin allow-forms`
- [x] 6.6 Add iframe loading state indicator
- [x] 6.7 Add iframe load failure error message
- [x] 6.8 Update `style.ts` with iframe panel styles (flex: 2, border, etc.)

## 7. Frontend - Management Page

- [x] 7.1 Create `console/src/pages/Control/Cases/index.tsx` - Management page
- [x] 7.2 Create `console/src/pages/Control/Cases/components/CaseDrawer.tsx` - Create/Edit form drawer
- [x] 7.3 Create `console/src/pages/Control/Cases/components/columns.tsx` - Table columns definition
- [x] 7.4 Create `console/src/pages/Control/Cases/components/hooks.ts` - useCases data management hook
- [x] 7.5 Create `console/src/pages/Control/Cases/index.module.less` - Page styles
- [x] 7.6 Implement case creation form with fields (ID, 标题, 提问内容, iframe_url, iframe_title, 步骤, 排序)
- [x] 7.7 Implement case editing form with pre-filled data
- [x] 7.8 Implement case deletion with confirmation modal
- [x] 7.9 Implement user assignment tab (userId -> case checkboxes)
- [x] 7.10 Add route in `console/src/layouts/MainLayout/index.tsx` for `/cases-management`
- [x] 7.11 Add menu item in Sidebar for "案例管理"

## 8. Localization and Documentation

- [x] 8.1 Add i18n translations in `console/src/locales/zh.json` (cases-management, createCase, editCase, etc.)
- [x] 8.2 Add i18n translations in `console/src/locales/en.json`
- [x] 8.3 Update CLAUDE.md if needed to document cases configuration