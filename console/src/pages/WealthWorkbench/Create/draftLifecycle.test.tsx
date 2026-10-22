import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Sidebar } from "../components/Sidebar";
import {
  fetchDistributeBranches,
  fetchDistributeTargets,
} from "../distributeTargets";
import { useWealthStore } from "../store";
import Create from "./index";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  fetchScenesByCategory: vi.fn().mockResolvedValue([]),
}));

vi.mock("../distributeTargets", () => ({
  fetchDistributeTargets: vi
    .fn()
    .mockResolvedValue([
      { sapId: "new-target", name: "可分发人员", orgName: "支行" },
    ]),
  fetchDistributeBranches: vi.fn().mockResolvedValue([]),
}));

beforeEach(() => {
  useWealthStore.setState({
    accountId: "rm",
    plansLoaded: false,
    plans: [],
    scenesByCategory: { "": [] },
    draft: {
      name: "旧规划",
      items: [
        {
          id: "old-scene",
          sceneName: "原经营场景",
          categoryLabel: "保险",
          categoryCode: "insurance",
          mcpRelations: [],
          direction: "原经营方向",
          cycle: "本月",
          start: "2026-10-01",
          end: "2026-10-31",
          schedule: { type: "daily", hour: 10, minute: 0 },
        },
      ],
    },
    editingId: "old-plan",
    savedAt: "10:00",
    targetSapIds: ["old-target"],
    targets: [{ sapId: "old-target", name: "原分发人员", orgName: "支行" }],
    targetsLoaded: true,
    targetBranch: null,
    branchTargetSapIds: ["old-target"],
    dialog: null,
    acting: false,
  });
});
afterEach(cleanup);

function renderWorkbench() {
  return render(
    <MemoryRouter initialEntries={["/wealth/create"]}>
      <Sidebar collapsed={false} onToggleCollapse={vi.fn()} />
      <Routes>
        <Route path="/wealth/create" element={<Create />} />
        <Route path="/wealth/board" element={<div>看板</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function expectEmptyForm() {
  expect(screen.getByLabelText("规划名称")).toHaveValue("");
  expect(useWealthStore.getState()).toMatchObject({
    draft: { name: "", items: [] },
    editingId: null,
    savedAt: "",
    targetSapIds: [],
    targets: [],
    targetsLoaded: false,
    targetBranch: null,
    branchTargetSapIds: [],
  });
}

it("修改页保留回填，点击创建计划即使路由不变也清空表单与分发目标", () => {
  renderWorkbench();
  expect(screen.getByLabelText("规划名称")).toHaveValue("旧规划");
  expect(screen.getByRole("heading", { name: "修改工作规划" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "创建计划" }));
  expectEmptyForm();
  expect(screen.getByRole("heading", { name: "新建工作规划" })).toBeVisible();
});

it("取消修改后再次创建进入空白表单", () => {
  renderWorkbench();
  fireEvent.click(screen.getByRole("button", { name: "取消" }));
  expect(useWealthStore.getState().draft).toEqual({ name: "", items: [] });
  fireEvent.click(screen.getByRole("button", { name: "创建计划" }));
  expectEmptyForm();
});

it("离开未发布的新建表单后草稿也清空", () => {
  useWealthStore.setState({ editingId: null });
  renderWorkbench();
  fireEvent.click(screen.getByRole("button", { name: "规划看板" }));
  expect(useWealthStore.getState().draft).toEqual({ name: "", items: [] });
});

it("行长在修改页直接新建后重新加载人员并清空搜索条件", async () => {
  useWealthStore.setState({ accountId: "president" });
  renderWorkbench();
  fireEvent.change(screen.getByLabelText("搜索分发目标"), {
    target: { value: "原分发人员" },
  });
  vi.mocked(fetchDistributeTargets).mockClear();
  fireEvent.click(screen.getByRole("button", { name: "创建计划" }));
  await waitFor(() => expect(fetchDistributeTargets).toHaveBeenCalledOnce());
  expect(screen.getByLabelText("搜索分发目标")).toHaveValue("");
  await screen.findByText("可分发人员");
  expect(useWealthStore.getState().targetSapIds).toEqual([]);
  expect(useWealthStore.getState().targetsLoaded).toBe(true);
});

it("中台直接新建后清除旧支行路径并重新查询支行", async () => {
  useWealthStore.setState({ accountId: "middle", plansLoaded: true });
  vi.mocked(fetchDistributeBranches).mockResolvedValue([
    { mOrgCode: "121516", mOrgName: "测试支行", mOrgLvl: 70, leaf: true },
  ]);
  renderWorkbench();
  const select = screen.getByRole("combobox", { name: "选择支行" });
  await waitFor(() => expect(select).toBeEnabled());
  fireEvent.mouseDown(select);
  fireEvent.click(
    await screen.findByRole("menuitemcheckbox", { name: /测试支行/ }),
  );
  await waitFor(() =>
    expect(useWealthStore.getState().targetsLoaded).toBe(true),
  );
  expect(screen.getByLabelText("搜索分发目标")).toBeEnabled();
  vi.mocked(fetchDistributeBranches).mockClear();
  fireEvent.click(screen.getByRole("button", { name: "创建计划" }));
  await waitFor(() => expect(fetchDistributeBranches).toHaveBeenCalledOnce());
  expect(screen.getByLabelText("搜索分发目标")).toBeDisabled();
  expect(useWealthStore.getState().targetBranch).toBeNull();
  expect(useWealthStore.getState().targetSapIds).toEqual([]);
});
