import React, { useState } from "react";
import Style from "./style";

export interface FeaturedCase {
  label: string;
  value: string;
  image?: string;
}

export interface FeaturedCasesProps {
  cases?: FeaturedCase[];
  onFillInput?: (text: string) => void;
  onViewCase?: (caseItem: FeaturedCase) => void;
}

const DEFAULT_CASES: FeaturedCase[] = [
  {
    label: "我想销售007119基金，请帮我找目标用户，并提供相应建议。",
    value: "我想销售007119基金，请帮我找目标用户，并提供相应建议。",
  },
  {
    label:
      '我要做存款经营，请基于历史本月到期流失，推测本月【他行存款到期】的潜力客户，按照"是谁、为什么、怎么做"提供给我。',
    value:
      '我要做存款经营，请基于历史本月到期流失，推测本月【他行存款到期】的潜力客户，按照"是谁、为什么、怎么做"提供给我。',
  },
  {
    label:
      "每天下午三点，收集今天的行情数据和重大市场资讯，如果某个板块跌5%以上，告诉我原因，以及哪些客户可能受到影响。",
    value:
      "每天下午三点，收集今天的行情数据和重大市场资讯，如果某个板块跌5%以上，告诉我原因，以及哪些客户可能受到影响。",
  },
  {
    label:
      "从三笔保单切入，帮我给【客户】做一份保障计划书，目标是让客户意识到保障缺口、进行加配。",
    value:
      "从三笔保单切入，帮我给【客户】做一份保障计划书，目标是让客户意识到保障缺口、进行加配。",
  },
  {
    label:
      "每天下午五点，向我发送今日业绩简报，需包含当日、当月的业绩数据、排名情况，并分析业绩缺口。",
    value:
      "每天下午五点，向我发送今日业绩简报，需包含当日、当月的业绩数据、排名情况，并分析业绩缺口。",
  },
];

function DocumentIcon() {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
      <rect x="7" y="3" width="5" height="18" rx="1" fill="currentColor" />
      <rect x="14" y="3" width="5" height="18" rx="1" fill="currentColor" />
      <rect x="7" y="3" width="12" height="1.5" fill="currentColor" />
    </svg>
  );
}

function MoreIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path
        d="M4 6.667L8 11L12 6.667"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function KYCIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="3" width="12.37" height="10.11" rx="1" fill="white" />
      <circle cx="5.07" cy="7.07" r="1.53" fill="white" />
      <rect x="7.9" y="9.17" width="4.2" height="2.5" rx="0.5" fill="white" />
      <rect
        x="7.07"
        y="4.63"
        width="3.31"
        height="1.04"
        rx="0.5"
        fill="white"
      />
      <rect x="9.6" y="6.21" width="2.74" height="1.04" rx="0.5" fill="white" />
    </svg>
  );
}

export default function FeaturedCases(props: FeaturedCasesProps) {
  const { cases = DEFAULT_CASES, onFillInput, onViewCase } = props;
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  const handleCardClick = (caseItem: FeaturedCase) => {
    onFillInput?.(caseItem.value);
  };

  const handleViewCase = (e: React.MouseEvent, caseItem: FeaturedCase) => {
    e.stopPropagation();
    onViewCase?.(caseItem);
  };

  const handleUseSame = (e: React.MouseEvent, caseItem: FeaturedCase) => {
    e.stopPropagation();
    onFillInput?.(caseItem.value);
  };

  return (
    <>
      <Style />
      <div className="featured-cases">
        <div className="featured-cases-header">
          <div className="featured-cases-title">
            <span className="featured-cases-title-icon">
              <DocumentIcon />
            </span>
            精选案例
          </div>
          <div className="featured-cases-more">
            查看更多
            <MoreIcon />
          </div>
        </div>
        <div className="featured-cases-scroll">
          {cases.map((caseItem) => (
            <div
              key={caseItem.value}
              className="featured-cases-card"
              onClick={() => handleCardClick(caseItem)}
              role="button"
              tabIndex={0}
            >
              {caseItem.image && (
                <img
                  className="featured-cases-card-image"
                  src={caseItem.image}
                  alt=""
                />
              )}
              <div className="featured-cases-card-text">{caseItem.label}</div>
              <div className="featured-cases-overlay">
                <button
                  className="featured-cases-overlay-btn"
                  onClick={(e) => handleViewCase(e, caseItem)}
                  type="button"
                >
                  <span className="featured-cases-overlay-btn-icon">
                    <KYCIcon />
                  </span>
                  看案例
                </button>
                <button
                  className="featured-cases-overlay-btn"
                  onClick={(e) => handleUseSame(e, caseItem)}
                  type="button"
                >
                  <span className="featured-cases-overlay-btn-icon">
                    <KYCIcon />
                  </span>
                  做同款
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
