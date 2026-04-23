## 1. Design Tokens & Style Foundation

- [x] 1.1 Add new design token constants (colors #3769FC, #8482E7, #FE2842, #F1F2F7, #11142D, #4F5060, #808191) to a shared style file or antd theme token
- [x] 1.2 Update page background color to #F1F2F7 in the Chat page container style

## 2. Knowledge Base Tabs Component

- [x] 2.1 Create `components/agentscope-chat/KnowledgeTabs/index.tsx` — pill-shaped tab bar with "原保险经验库"/"分行经验库", active state purple #8482E7, inactive #333, vertical divider between tabs
- [x] 2.2 Create `components/agentscope-chat/KnowledgeTabs/style.ts` — CSS-in-JS styles (border-radius 20, height 28px, gap 16px)
- [x] 2.3 Implement local tab switching state (UI only, no API calls)

## 3. Featured Case Cards Component

- [x] 3.1 Create `components/agentscope-chat/FeaturedCases/index.tsx` — section with header ("精选案例" + "查看更多") and horizontal scrollable card row
- [x] 3.2 Create `components/agentscope-chat/FeaturedCases/style.ts` — card dimensions 176x168px, white bg, border-radius, 12px gap, horizontal overflow scroll
- [x] 3.3 Implement case card content: optional image thumbnail (75x53) + truncated text description (#4F5060)
- [x] 3.4 Implement hover overlay: semi-transparent black mask (rgba(0,0,0,0.6)) with two pill buttons "看案例"/"做同款" (bg #3769FC, radius 100, white text)
- [x] 3.5 Implement "做同款" click handler — fill case text into parent input box via callback prop
- [x] 3.6 Implement "看案例" click handler — placeholder expand/detail view (UI skeleton)
- [x] 3.7 Implement card body click — fill case text into input box (same as "做同款" behavior)

## 4. Welcome Page Layout Restructure

- [x] 4.1 Create `components/agentscope-chat/WelcomeCenterLayout/index.tsx` — custom welcome render component: vertically centered layout with greeting → input card → KnowledgeTabs → FeaturedCases
- [x] 4.2 Create `components/agentscope-chat/WelcomeCenterLayout/style.ts` — flex column center, max-width 800px, gap spacing per design
- [x] 4.3 Implement greeting section: font-size 22px, color #333, configurable text
- [x] 4.4 Implement centered input card: white bg, radius 12px, width 800px, contains Sender component with placeholder text, attachment button, send button (32x32, bg #3769FC)
- [x] 4.5 Connect input card Sender to chat submission flow via ChatAnywhereInputContext or event emitter
- [x] 4.6 Integrate KnowledgeTabs below input card in the welcome layout
- [x] 4.7 Integrate FeaturedCases below tabs in the welcome layout, passing prompts data and click-to-fill callback

## 5. ChatPage Integration

- [x] 5.1 Update `pages/Chat/index.tsx` options.welcome.render to use WelcomeCenterLayout instead of default WelcomePrompts
- [x] 5.2 Hide default Sender when welcome layout is active (welcome state shows centered sender, chat state shows bottom sender)
- [x] 5.3 Ensure prompt data (welcome.prompts) flows through to FeaturedCases component
- [x] 5.4 Verify Enter key and send button both work in the welcome-centered input card
- [x] 5.5 Verify message submission transitions from welcome layout to message list + bottom sender

## 6. Sidebar Task List Component

- [x] 6.1 Create `pages/Chat/components/ChatTaskList/index.tsx` — collapsible "我的任务(N)" section with task items
- [x] 6.2 Create `pages/Chat/components/ChatTaskList/style.ts` — section styles matching sidebar design
- [x] 6.3 Implement task data fetching from cronjob API (`cronjobApi.listCronJobs()`)
- [x] 6.4 Implement task item rendering: title (#11142D), subtitle (#808191), optional red badge (#FE2842) with count
- [x] 6.5 Implement task item click handler — trigger cronjob execution via `cronjobApi.triggerCronJob(id)` and send task content as chat message
- [x] 6.6 Implement collapsible section toggle (expand/collapse icon)

## 7. Sidebar History Section Restyle

- [x] 7.1 Add "历史记录(N)" section header to the sidebar session list with collapse toggle
- [x] 7.2 Update history item style: title (#4F5060), timestamp in "YYYY-MM-DD HH:mm" format (#808191)
- [x] 7.3 Maintain existing session click-to-navigate behavior

## 8. Sidebar Bottom Toolbar & New Topic Button

- [x] 8.1 Create sidebar footer component with "skill市场" and "操作指南" links separated by vertical divider
- [x] 8.2 Restyle "新建聊天" button: pill shape (border-radius 100), background #3769FC, white text, "+" icon
- [x] 8.3 Integrate task list, history section, new topic button, and footer toolbar into the sidebar layout

## 9. Integration Testing & Polish

- [x] 9.1 Test welcome layout → chat transition: send first message, verify welcome disappears and message list + bottom sender appear
- [x] 9.2 Test featured case card click fills input, then user can edit and send
- [x] 9.3 Test "做同款" button fills input correctly
- [x] 9.4 Test sidebar task click triggers cronjob and creates chat message
- [x] 9.5 Test responsive behavior: layout adapts when sidebar is hidden (iframe mode)
- [x] 9.6 Verify dark mode compatibility for all new components
- [x] 9.7 Verify all color values match design spec exactly
