import { createContext } from "use-context-selector";

// 保留 Context 以备未来扩展，当前猜你想问功能无开关状态管理
const SuggestionsContext = createContext<Record<string, unknown>>({});

export { SuggestionsContext };
export default SuggestionsContext;