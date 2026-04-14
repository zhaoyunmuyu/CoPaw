import React, { useState } from 'react';
import Style from './style';

export interface KnowledgeTab {
  key: string;
  label: string;
}

export interface KnowledgeTabsProps {
  tabs?: KnowledgeTab[];
  defaultActiveKey?: string;
  onChange?: (activeKey: string) => void;
}

const DEFAULT_TABS: KnowledgeTab[] = [
  { key: 'insurance', label: '原保险经验库' },
  { key: 'branch', label: '分行经验库' },
];

export default function KnowledgeTabs(props: KnowledgeTabsProps) {
  const { tabs = DEFAULT_TABS, defaultActiveKey, onChange } = props;
  const [activeKey, setActiveKey] = useState(
    defaultActiveKey || tabs[0]?.key || '',
  );

  const handleTabClick = (key: string) => {
    if (key !== activeKey) {
      setActiveKey(key);
      onChange?.(key);
    }
  };

  return (
    <>
      <Style />
      <div className="knowledge-tabs">
        {tabs.map((tab, index) => (
          <React.Fragment key={tab.key}>
            <button
              className={`knowledge-tabs-item ${
                activeKey === tab.key
                  ? 'knowledge-tabs-item--active'
                  : 'knowledge-tabs-item--inactive'
              }`}
              onClick={() => handleTabClick(tab.key)}
              type="button"
            >
              {activeKey === tab.key && (
                <span className="knowledge-tabs-icon">
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 14 14"
                    fill="none"
                  >
                    <path
                      d="M11.6667 3.5L5.25 9.91667L2.33333 7"
                      stroke="#F7F7FC"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
              )}
              {tab.label}
            </button>
            {index < tabs.length - 1 && (
              <div className="knowledge-tabs-divider" />
            )}
          </React.Fragment>
        ))}
      </div>
    </>
  );
}
