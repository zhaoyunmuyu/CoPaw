import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Plan, PlanItem } from "../types";
import { Calendar } from "./Calendar";
import { addCalendarDays, todayKey } from "../utils";
import styles from "../index.module.less";

function makeItem(id: string, sceneName: string, start: string): PlanItem {
  return {
    id,
    sceneName,
    categoryLabel: "理财",
    categoryCode: "finance",
    mcpRelations: [],
    direction: "客户经营",
    cycle: "自定义",
    start,
    end: start,
    schedule: { type: "daily", hour: 9, minute: 0 },
  };
}

const PLAN: Plan = {
  id: "plan-1",
  name: "九月重点规划",
  source: "我的关注",
  desc: "测试规划",
  customers: 10,
  tasks: 2,
  rate: 20,
  status: "已自动下发",
  period: "本月",
  start: "2026-09-01",
  end: "2026-09-30",
  items: [
    makeItem("scene-1", "高净值客户经营", "2026-09-14"),
    makeItem("scene-2", "理财到期提醒", "2026-09-15"),
  ],
};

describe("Calendar", () => {
  afterEach(cleanup);

  it.each(["week", "month"] as const)(
    "%s 仅今天的已发布有效规划展示名单入口，选择首个当天场景且不触发详情",
    (dimension) => {
      const day = todayKey();
      const yesterday = addCalendarDays(day, -1);
      const tomorrow = addCalendarDays(day, 1);
      const plan: Plan = {
        ...PLAN,
        publishStatus: "published",
        start: yesterday,
        end: tomorrow,
        items: [
          makeItem("past", "昨日场景", yesterday),
          makeItem("first", "同名场景", day),
          makeItem("second", "同名场景", day),
          makeItem("future", "明日场景", tomorrow),
        ],
      };
      const onShowDetails = vi.fn();
      const onViewCustomers = vi.fn();
      const props = {
        sources: ["我的关注"],
        visible: [plan],
        planStat: () => null,
        dimension,
        anchor: day,
        onShift: vi.fn(),
        onToday: vi.fn(),
        onDimension: vi.fn(),
        onShowDetails,
        onViewCustomers,
      };
      const { rerender } = render(<Calendar {...props} />);
      const jump = screen.getByRole("button", {
        name: `查看「${plan.name}」客户名单`,
      });
      expect(jump.closest("[data-date]")).toHaveAttribute("data-date", day);
      expect(jump.parentElement?.closest("button")).toBeNull();
      if (dimension === "month") {
        const event = jump.parentElement!.querySelector(
          `.${styles.calendarEvent}`,
        )!;
        expect(event.querySelector(`.${styles.calendarFrequency}`)).toBeNull();
      }
      fireEvent.click(jump);
      expect(onViewCustomers).toHaveBeenCalledExactlyOnceWith("first");
      expect(onShowDetails).not.toHaveBeenCalled();
      for (const publishStatus of ["publishing", "publish_failed"]) {
        rerender(
          <Calendar {...props} visible={[{ ...plan, publishStatus }]} />,
        );
        expect(
          screen.queryByRole("button", { name: /客户名单/ }),
        ).not.toBeInTheDocument();
      }
      rerender(<Calendar {...props} onViewCustomers={undefined} />);
      expect(
        screen.queryByRole("button", { name: /客户名单/ }),
      ).not.toBeInTheDocument();
      if (dimension === "month") {
        for (const event of screen.getAllByRole("button", {
          name: /点击查看详情/,
        })) {
          expect(
            event.querySelector(
              `.${styles.calendarEventTitle} .${styles.calendarFrequency}`,
            ),
          ).not.toBeNull();
        }
      }
    },
  );

  it.each(["week", "month"] as const)(
    "%s 日历按维度展示标题与经营场景，保留当天详情入口",
    async (dimension) => {
      const onShowDetails = vi.fn();
      render(
        <Calendar
          sources={["分行关注", "行长关注", "我的关注"]}
          visible={[PLAN]}
          planStat={() => null}
          dimension={dimension}
          anchor="2026-09-14"
          onShift={vi.fn()}
          onToday={vi.fn()}
          onDimension={vi.fn()}
          onShowDetails={onShowDetails}
        />,
      );

      const events = screen.getAllByRole("button", {
        name: `${PLAN.name}，2 个技能，点击查看详情`,
      });
      expect(events).toHaveLength(2);
      expect(screen.getAllByText(PLAN.name)).toHaveLength(2);
      for (const event of events) {
        expect(event.querySelector("strong")).toHaveTextContent(PLAN.name);
        expect(event).not.toHaveAttribute("title");
      }
      if (dimension === "week") {
        expect(
          screen.getAllByText("经营场景：高净值客户经营，理财到期提醒"),
        ).toHaveLength(2);
        expect(screen.queryByLabelText("2 个技能")).toBeNull();
      } else {
        expect(screen.getAllByLabelText("2 个技能")).toHaveLength(2);
        for (const count of screen.getAllByLabelText("2 个技能")) {
          expect(count).toHaveTextContent("2");
        }
        expect(screen.queryByText(/^经营场景：/)).toBeNull();
      }
      fireEvent.mouseEnter(events[0]);
      const tooltip = await screen.findByRole("tooltip");
      expect(
        within(tooltip).getByText(`规划名称：${PLAN.name}`),
      ).toBeInTheDocument();
      expect(
        within(tooltip).getByText("经营场景：高净值客户经营，理财到期提醒"),
      ).toBeInTheDocument();
      fireEvent.click(events[0]);
      expect(onShowDetails).toHaveBeenCalledWith("2026-09-14", PLAN.id);
      fireEvent.click(events[1]);
      expect(onShowDetails).toHaveBeenCalledWith("2026-09-15", PLAN.id);
    },
  );
});
