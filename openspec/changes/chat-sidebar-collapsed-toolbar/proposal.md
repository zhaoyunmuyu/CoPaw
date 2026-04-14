## Why

The chat sidebar currently uses a wide 308px panel layout even in its collapsed state. The new Pixso design specifies a slim 64px collapsed toolbar that shows only icon buttons (new chat, tasks, history) with hover tooltips and expandable sub-panels. This provides a more space-efficient interface while preserving all functionality.

## What Changes

- Replace the current collapsed sidebar behavior (icon-only global nav) with a dedicated 64px collapsed chat toolbar containing 3 icon buttons: new chat (新建聊天), tasks (我的任务), history (历史记录)
- Add hover tooltips (dark semi-transparent, left-pointing arrow) for each icon button
- Add expandable sub-panels (308px wide) that slide out to the right of the toolbar when a section icon is clicked — panels for tasks and history
- Add notification badge (red pill, #FE2842) on the tasks icon when there are unread task alerts
- Style task items as bordered cards (0.5px #E4E4E4, radius 8) with title + subtitle + optional badge
- Style history items as plain text rows (no border/card styling) with title + timestamp
- Active icon highlighted with #3769FC, inactive icons in #808191

## Capabilities

### New Capabilities
- `collapsed-toolbar`: 64px collapsed sidebar toolbar with icon buttons, hover tooltips, active state highlighting, and notification badges
- `expandable-panels`: Sub-panels that slide out from the collapsed toolbar showing task list and history records with proper styling

### Modified Capabilities
<!-- No existing spec-level requirements are changing -->

## Impact

- `console/src/pages/Chat/components/ChatSidebar/` — major rework to support collapsed toolbar mode
- `console/src/pages/Chat/components/ChatTaskList/` — styling updates to match card-based task design
- `console/src/pages/Chat/components/ChatSidebar/style.ts` — new styles for 64px toolbar, tooltips, expandable panels
- `console/src/pages/Chat/index.tsx` — layout adjustments for collapsed toolbar coexistence
- `console/src/config/designTokens.ts` — new tokens for toolbar dimensions, badge colors, tooltip styles
