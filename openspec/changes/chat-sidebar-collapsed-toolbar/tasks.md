## 1. Design Tokens & Constants

- [x] 1.1 Add new tokens to `designTokens.ts`: toolbar width (64), toolbar icon size (28), toolbar icon gap (24), panel width (308), panel gap (8), panel padding (20), tooltip background color, badge font size (10), card border color (#E4E4E4)
- [x] 1.2 Add SVG icon components for collapsed toolbar: NewChatIcon (plus/cross 21x21), TasksIcon (clock/timer 20x24), HistoryIcon (clock+rewind 21x20) — each accepting active/inactive color prop

## 2. Collapsed Toolbar Component

- [x] 2.1 Create `ChatSidebar/CollapsedToolbar/index.tsx` — 64px wide toolbar with 3 vertically-stacked icon buttons, accepts `activePanel` and `onIconClick` props, renders notification badge on Tasks icon
- [x] 2.2 Create `ChatSidebar/CollapsedToolbar/style.ts` — toolbar container (64px, white bg, right border #E4E4E4, shadow), icon button container (28x28 icons, 24px gap, 18px left padding, 24px top padding), badge styles (red pill #FE2842)
- [x] 2.3 Add hover tooltips to each icon button using Ant Design Tooltip with dark custom styling (rgba(0,0,0,0.6) background, 4px radius, white text 14px — scaled from design 20px to fit UI density)

## 3. Expandable Panels

- [x] 3.1 Create `ChatSidebar/ExpandablePanel/index.tsx` — container component that renders panel content 8px to the right of the toolbar, supports click-outside-to-close, accepts `visible`, `onClose` props
- [x] 3.2 Create `ChatSidebar/ExpandablePanel/style.ts` — panel container (308px, white bg, radius 8px, padding 20px, z-index 100), header styles (16px semibold, gap 4, icon 16x16)
- [x] 3.3 Create TasksPanel content — renders task list with bordered card items (0.5px border #E4E4E4, radius 8px, padding 12px, gap 8px), each with title + badge + subtitle. Badge: red pill (#FE2842), 10px white text, radius 12px
- [x] 3.4 Create HistoryPanel content — renders session list as plain text rows (no card/border), title 16px #4F5060, timestamp 12px #808191, padding 10px top/bottom, hover highlight

## 4. ChatSidebar Integration

- [x] 4.1 Refactor `ChatSidebar/index.tsx` to accept `collapsed` prop — when true renders CollapsedToolbar + expandable panels, when false renders existing full sidebar
- [x] 4.2 Add `activePanel` state management in ChatSidebar — tracks which panel is open ('tasks' | 'history' | null), toggling logic, click-outside-to-close
- [x] 4.3 Update `ChatSidebar/style.ts` — add styles for collapsed mode wrapper, panel overlay positioning, and transition for panel appear/disappear

## 5. Parent Integration

- [x] 5.1 Update `Chat/index.tsx` to pass `collapsed` prop to ChatSidebar based on sidebar collapse state, and wire up the collapse toggle
- [x] 5.2 Verify toolbar + panels coexist correctly with the global sidebar and chat area layout (no z-index conflicts, no layout shifts)

## 6. Styling Polish

- [ ] 6.1 Verify all pixel values match design spec: toolbar 64px, icons 28x28, gap 24px, panel 308px, panel gap 8px, card border 0.5px #E4E4E4, card radius 8px, badge radius 12px
- [ ] 6.2 Ensure click-outside detection works correctly (clicking chat area closes panel, clicking toolbar icon toggles correctly)
