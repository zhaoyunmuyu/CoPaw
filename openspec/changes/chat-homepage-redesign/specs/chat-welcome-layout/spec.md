## ADDED Requirements

### Requirement: Welcome page center-aligned layout
The welcome page SHALL display a vertically centered layout with the following top-to-bottom order: greeting text, input box card, knowledge base tabs, and featured case cards section.

#### Scenario: Initial state with no messages
- **WHEN** the chat page loads with no existing messages
- **THEN** the welcome layout is displayed centered in the main content area with greeting, input box, tabs, and case cards visible

#### Scenario: After first message sent
- **WHEN** the user sends the first message
- **THEN** the welcome layout is hidden and replaced by the standard message list with bottom input bar

### Requirement: Greeting text styling
The greeting text SHALL display with font-size 22px, color #333333, centered alignment. The default text is "你好，你的专属小龙虾，前来报到！" but SHALL be configurable via `welcome.greeting`.

#### Scenario: Default greeting display
- **WHEN** no custom greeting is provided
- **THEN** the greeting "你好，你的专属小龙虾，前来报到！" is displayed with fontSize 22px and color #333

#### Scenario: Custom greeting from config
- **WHEN** a custom greeting is provided via `welcome.greeting`
- **THEN** the custom text is displayed with the same styling

### Requirement: Centered input box card
The input box SHALL be displayed as a white card (background #FFFFFF, border-radius 12px, width 800px max) centered in the welcome layout. It SHALL contain a placeholder description text, an attachment button, and a send button (background #3769FC, size 32x32).

#### Scenario: Empty input state
- **WHEN** the input box is displayed with no text
- **THEN** the placeholder "告诉我你要做什么，我将召唤相应专家，为你执行…" is shown in color #808191

#### Scenario: Filling input from featured case
- **WHEN** a user clicks a featured case card or the "做同款" button
- **THEN** the case text is filled into the input box without auto-sending

#### Scenario: User types and sends
- **WHEN** the user types text in the input box and presses Enter or clicks the send button
- **THEN** the message is submitted via the existing chat submission flow

### Requirement: New topic button pill style
The "新建聊天" button SHALL use a pill/capsule style with border-radius 100px, background #3769FC, and white text. It SHALL include a "+" icon.

#### Scenario: New topic button display
- **WHEN** the sidebar is visible
- **THEN** the "新建聊天" button is displayed with pill shape, blue background, and white text

### Requirement: Sidebar footer toolbar
The sidebar SHALL display a footer section at the bottom with two entry links: "skill市场" and "操作指南", separated by a vertical divider. Each link SHALL have an icon and text label.

#### Scenario: Footer toolbar display
- **WHEN** the sidebar is visible
- **THEN** "skill市场" and "操作指南" are displayed at the sidebar bottom with icons and labels

### Requirement: Page background color
The main content area (behind the welcome layout) SHALL use background color #F1F2F7.

#### Scenario: Background rendering
- **WHEN** the chat welcome page is displayed
- **THEN** the content area background is #F1F2F7
