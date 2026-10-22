import { beforeEach, expect, it, vi } from "vitest";
import * as api from "./api";
import { fetchDistributeTargets } from "./distributeTargets";
import { useWealthStore } from "./store";
import type { DistributeTarget } from "./types";
import { cycleRange } from "./utils";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  publishPlan: vi.fn(),
}));
vi.mock("./distributeTargets", () => ({ fetchDistributeTargets: vi.fn() }));

beforeEach(() => {
  vi.resetAllMocks();
  useWealthStore.getState().resetPlanForm();
  const [start, end] = cycleRange("本月")!;
  useWealthStore.setState({
    accountId: "rm",
    acting: false,
    plans: [],
    draft: {
      name: "旧计划",
      items: [
        {
          id: "scene-1",
          sceneName: "场景",
          categoryLabel: "保险",
          categoryCode: "insurance",
          mcpRelations: [],
          direction: "原方向",
          cycle: "本月",
          start,
          end,
          schedule: { type: "daily", hour: 10, minute: 0 },
        },
      ],
    },
    editingId: "old-plan",
  });
});

it("发布失败保留原表单、修改 ID 和分发目标供重试", async () => {
  vi.mocked(api.publishPlan).mockRejectedValue(new Error("服务不可用"));
  useWealthStore.setState({ targetSapIds: ["old-target"] });
  const draft = useWealthStore.getState().draft;
  expect(await useWealthStore.getState().publishPlan()).toBe(false);
  expect(useWealthStore.getState()).toMatchObject({
    draft,
    editingId: "old-plan",
    targetSapIds: ["old-target"],
    acting: false,
  });
});

it("清空表单后旧人员请求返回不会回填人员", async () => {
  let resolve!: (targets: DistributeTarget[]) => void;
  vi.mocked(fetchDistributeTargets).mockReturnValue(
    new Promise((r) => {
      resolve = r;
    }),
  );
  const loading = useWealthStore.getState().loadTargets();
  useWealthStore.getState().resetPlanForm();
  resolve([{ sapId: "old-target", name: "旧人员", orgName: "支行" }]);
  await loading;
  expect(useWealthStore.getState().targets).toEqual([]);
  expect(useWealthStore.getState().targetsLoaded).toBe(false);
});

it("离开旧表单后发布请求完成不会覆盖新表单或触发成功跳转", async () => {
  let resolve!: (result: api.PublishResult) => void;
  vi.mocked(api.publishPlan).mockReturnValue(
    new Promise((r) => {
      resolve = r;
    }),
  );
  const publishing = useWealthStore.getState().publishPlan();
  useWealthStore.getState().resetPlanForm();
  useWealthStore.getState().setDraftName("新的未发布计划");
  resolve({ plans: [], created: false });
  expect(await publishing).toBe(false);
  expect(useWealthStore.getState().draft).toEqual({
    name: "新的未发布计划",
    items: [],
  });
  expect(useWealthStore.getState().acting).toBe(false);
});

it("正常发布成功仍返回成功，保留最新规划列表", async () => {
  vi.mocked(api.publishPlan).mockResolvedValue({ plans: [], created: false });
  expect(await useWealthStore.getState().publishPlan()).toBe(true);
  expect(useWealthStore.getState().editingId).toBeNull();
  expect(useWealthStore.getState().acting).toBe(false);
});

it("取消表单时关闭旧发布确认框", () => {
  useWealthStore
    .getState()
    .openDialog({ title: "发布工作规划", body: null, buttons: [] });
  useWealthStore.getState().resetPlanForm();
  expect(useWealthStore.getState().dialog).toBeNull();
});
