import React, { useState, useEffect, useCallback } from "react";
import { cronJobApi } from "@/api/modules/cronjob";
import type { CronJobSpecOutput } from "@/api/types";
import Style from "./style";
import { DESIGN_TOKENS } from "@/config/designTokens";

function TaskIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path
        d="M2.29 4.3L8 1.05L13.71 4.3V11.7L8 14.95L2.29 11.7V4.3Z"
        stroke={DESIGN_TOKENS.colorTextPrimary}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ToggleIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg
      width="10"
      height="6"
      viewBox="0 0 10 6"
      fill="none"
      className={`chat-task-list-toggle${
        collapsed ? " chat-task-list-toggle--collapsed" : ""
      }`}
    >
      <path
        d="M1 1L5 5L9 1"
        stroke={DESIGN_TOKENS.colorTextMuted}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export interface ChatTaskListProps {
  onTaskClick?: (task: CronJobSpecOutput) => void;
}

export default function ChatTaskList(props: ChatTaskListProps) {
  const { onTaskClick } = props;
  const [tasks, setTasks] = useState<CronJobSpecOutput[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    cronJobApi
      .listCronJobs()
      .then((data) => {
        setTasks(Array.isArray(data) ? data : []);
      })
      .catch(() => {
        setTasks([]);
      });
  }, []);

  const handleToggle = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const handleTaskClick = useCallback(
    (task: CronJobSpecOutput) => {
      onTaskClick?.(task);
      cronJobApi.triggerCronJob(task.id).catch(() => {});
    },
    [onTaskClick],
  );

  return (
    <>
      <Style />
      <div className="chat-task-list">
        <div
          className="chat-task-list-header"
          onClick={handleToggle}
          role="button"
          tabIndex={0}
        >
          <div className="chat-task-list-title">
            <TaskIcon />
            我的任务({tasks.length})
          </div>
          <ToggleIcon collapsed={collapsed} />
        </div>
        {!collapsed && (
          <div className="chat-task-list-items">
            {tasks.length === 0 ? (
              <div className="chat-task-list-empty">暂无任务</div>
            ) : (
              tasks.map((task) => (
                <div
                  key={task.id}
                  className="chat-task-list-item"
                  onClick={() => handleTaskClick(task)}
                  role="button"
                  tabIndex={0}
                >
                  <div className="chat-task-list-item-header">
                    <span className="chat-task-list-item-title">
                      {task.name || task.text || task.id}
                    </span>
                    {/* Badge placeholder: will be driven by unread count when API supports it */}
                  </div>
                  {task.text && task.name && (
                    <div className="chat-task-list-item-subtitle">
                      {task.text}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </>
  );
}
