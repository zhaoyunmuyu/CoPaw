## Context

The chat page currently has a 308px wide ChatSidebar component that is always fully expanded, showing task list, history records, new-topic button, and footer toolbar in a single column. The Pixso design specifies that when the chat sidebar is "collapsed", it should become a slim 64px icon-only toolbar with 3 buttons (new chat, tasks, history), with expandable sub-panels sliding out on click.

The current ChatSidebar component (`console/src/pages/Chat/components/ChatSidebar/`) already renders the expanded layout. We need to add a collapsed mode that shows only the 64px toolbar, with the existing expanded content appearing in slide-out panels.

Key constraint: The global sidebar (MainLayout) and the chat sidebar are separate components. The collapsed toolbar only applies to the chat-specific sidebar.

## Goals / Non-Goals

**Goals:**
- Implement a 64px collapsed toolbar mode for ChatSidebar with 3 icon buttons
- Add hover tooltips (dark semi-transparent, left-pointing arrow) for each icon
- Implement expandable sub-panels (308px) that slide out to the right of the toolbar
- Style task items as bordered cards matching the design spec
- Style history items as plain text rows matching the design spec
- Add notification badge support on the tasks icon

**Non-Goals:**
- Modifying the global MainLayout sidebar collapse behavior
- Dark mode support for the collapsed toolbar (can be added later)
- Animating the collapse/expand transition of the sidebar itself (toolbar is always 64px when collapsed)
- Modifying the expanded ChatSidebar layout (it already exists and works)

## Decisions

### 1. Component Architecture: Overlay Panels vs Inline Expansion

**Decision**: Use overlay panels positioned absolutely/fixed to the right of the 64px toolbar.

**Rationale**: The expanded panels (tasks, history) should float over the chat area without pushing content. The design shows them as separate white cards with 8px gap from the toolbar, shadow, and border-radius 8px. Using overlay positioning keeps the main chat area stable.

**Alternative considered**: Inline expansion (toolbar width grows to accommodate panel). Rejected because it would shift the chat area and the design clearly shows panels floating over content.

### 2. Tooltip Implementation: CSS-only vs Component Library

**Decision**: Use Ant Design's `Tooltip` component with custom dark styling.

**Rationale**: Already available in the project, supports positioning and delays. We override the background to `rgba(0, 0, 0, 0.6)` and border-radius to 4px to match the design. The left-pointing arrow is handled by Tooltip's `placement="right"`.

### 3. Panel State Management

**Decision**: Local state in ChatSidebar — `activePanel: 'tasks' | 'history' | null`.

**Rationale**: Panel state is UI-only, doesn't need to be persisted or shared. Clicking the same icon again toggles the panel closed. Clicking a different icon switches panels. Clicking outside closes the panel.

### 4. Collapsed vs Expanded Mode Control

**Decision**: ChatSidebar receives a `collapsed` prop. The parent (ChatPage) controls this state. When collapsed=true, only the 64px toolbar renders. When collapsed=false, the existing full 308px sidebar renders.

**Rationale**: Clean separation — the parent decides layout, the child renders accordingly. This avoids duplicating content between two separate components.

### 5. Styling Approach

**Decision**: Continue using `createGlobalStyle` from `antd-style` (matching existing pattern in ChatSidebar/style.ts and ChatTaskList/style.ts).

**Rationale**: Consistency with existing codebase. The current ChatSidebar and ChatTaskList already use this pattern.

## Risks / Trade-offs

- **[Click-outside detection]** → Use a `useEffect` with `document.addEventListener('mousedown')` to close panels when clicking outside both the toolbar and the open panel.
- **[Panel z-index]** → Panel must render above chat content but below modals. Use `z-index: 100` which is below Ant Design modal defaults (1000+).
- **[Notification badge data]** → The tasks badge count requires unread notification data from the API. Until the API supports it, show the badge with a static count or hide it. Mark as placeholder.
- **[Mobile responsiveness]** → The 64px toolbar + 308px panel = 372px total width. On narrow screens this may be too wide. For now, desktop-only; mobile adaptation is out of scope.
