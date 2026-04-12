import React from 'react';
import { DESIGN_TOKENS } from '@/config/designTokens';

interface IconProps {
  active?: boolean;
}

const ACTIVE_COLOR = DESIGN_TOKENS.colorPrimary;
const INACTIVE_COLOR = DESIGN_TOKENS.colorIconInactive;

/** Plus/cross icon — "新建聊天" button */
export function NewChatIcon({ active = false }: IconProps) {
  const color = active ? ACTIVE_COLOR : INACTIVE_COLOR;
  return (
    <svg width="21" height="21" viewBox="0 0 21 21" fill="none">
      <path
        d="M10.5 1V20M1 10.5H20"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Clock/timer icon — "我的任务" button */
export function TasksIcon({ active = false }: IconProps) {
  const color = active ? ACTIVE_COLOR : INACTIVE_COLOR;
  return (
    <svg width="20" height="24" viewBox="0 0 20 24" fill="none">
      <circle
        cx="10"
        cy="14"
        r="9"
        stroke={color}
        strokeWidth="1.5"
      />
      <path
        d="M10 9V14L13 16"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M7 1H13"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M10 1V5"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Clock with rewind arrow — "历史记录" button */
export function HistoryIcon({ active = false }: IconProps) {
  const color = active ? ACTIVE_COLOR : INACTIVE_COLOR;
  return (
    <svg width="21" height="20" viewBox="0 0 21 20" fill="none">
      <path
        d="M3.5 4C5.1 1.8 7.7 0.5 10.5 0.5C15.5 0.5 19.5 4.5 19.5 9.5C19.5 14.5 15.5 18.5 10.5 18.5C6.3 18.5 2.8 15.6 1.8 11.7"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      <path
        d="M1.5 4V8H5.5"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M10.5 5V10L14 11.5"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Small 16x16 tasks icon for panel headers */
export function TasksIconSmall({ active = false }: IconProps) {
  const color = active ? ACTIVE_COLOR : DESIGN_TOKENS.colorTextPrimary;
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="9" r="6" stroke={color} strokeWidth="1.2" />
      <path d="M8 6V9L10 10.5" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M5.5 1H10.5" stroke={color} strokeWidth="1.2" strokeLinecap="round" />
      <path d="M8 1V3.5" stroke={color} strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
}

/** Small 16x16 history icon for panel headers */
export function HistoryIconSmall({ active = false }: IconProps) {
  const color = active ? ACTIVE_COLOR : DESIGN_TOKENS.colorTextPrimary;
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M3 3.5C4.2 1.8 6.3 0.7 8.5 0.7C12.4 0.7 15.5 3.8 15.5 7.7C15.5 11.6 12.4 14.7 8.5 14.7C5.3 14.7 2.6 12.5 1.8 9.5" stroke={color} strokeWidth="1.2" strokeLinecap="round" />
      <path d="M1.5 3V6H4.5" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M8.5 4V7.5L11 9" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
