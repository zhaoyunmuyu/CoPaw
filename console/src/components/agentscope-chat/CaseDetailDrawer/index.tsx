import React from 'react';
import { Drawer } from 'antd';
import Style from './style';
import { DESIGN_TOKENS } from '@/config/designTokens';

export interface CaseDetailData {
  title: string;
  value: string;
  tableTitle?: string;
  tableHeaders?: string[];
  tableRows?: string[][];
  steps?: { title: string; content: string }[];
}

export interface CaseDetailDrawerProps {
  visible: boolean;
  onClose: () => void;
  caseData: CaseDetailData | null;
  onMakeSimilar?: (value: string) => void;
}

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path
        d="M1 1L13 13M13 1L1 13"
        stroke="#999999"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SubscribeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.2" />
      <path
        d="M8 4.5V8.5L10.5 10"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function NewSessionIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path
        d="M8 3V13M3 8H13"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function CaseDetailDrawer({
  visible,
  onClose,
  caseData,
  onMakeSimilar,
}: CaseDetailDrawerProps) {
  const handleMakeSimilar = () => {
    if (caseData) {
      onMakeSimilar?.(caseData.value);
    }
    onClose();
  };

  // Default sample data from Pixso design
  const tableHeaders = caseData?.tableHeaders || [
    '姓名',
    '推荐理由',
    '时点AUM',
    '最近接触时间',
    '操作',
  ];

  const tableRows = caseData?.tableRows || [
    ['史仪', '客户存款到期及转出行为...', '150.09万', '2025-12-30'],
    ['毛荣', '客户存款到期及转出行为...', '140.09万', '2025-12-30'],
    ['沈彩', '客户存款到期及转出行为...', '130.09万', '2025-12-30'],
    ['程枝', '客户存款到期及转出行为...', '130.09万', '2025-12-30'],
  ];

  const steps = caseData?.steps || [
    {
      title: '步骤1：入池——筛选本月可能有他行存款到期的客户',
      content:
        '①1年、2年、3年前的本月有我行定期存款到期，该月累计到期金额>5万，且存款到期7天内发生他行大额转出；\n②1年、2年、3年前的本月有他行同名大额转出，且客户历史/现在持有定期存款；\n③剔除过账客户；',
    },
    {
      title: '步骤2：优先级——客户存款配置潜力分析，综合以下因素打分排序',
      content:
        '①到期金额及转出对象：到期和转出的金额、转出的银行当地当月到期规模\n②客户持仓分析：客户持仓是否保守、客户是否交易不活跃、是否命中存款偏好标签\n③客户接触分析：流失时客户是否抱怨利率或提及转出\n④客户APP行为：客户最近是否有存款频道浏览行为\n⑤存款预约行为：是否为客户预约过定期存款\n⑥营销黑名单：命中营销黑名单的优先级将靠后',
    },
    {
      title: '步骤3：最终名单——整理清晰的推荐客户列表',
      content:
        '①客户的资金流失行为\n②高优推荐理由\n③客户时点AUM\n④最近接触时间',
    },
  ];

  return (
    <>
      <Style />
      <Drawer
        className="case-detail-drawer"
        placement="bottom"
        open={visible}
        onClose={onClose}
        height="90%"
        closable={false}
        maskClosable
        styles={{
          body: { padding: 0, overflow: 'hidden' },
        }}
      >
        {/* Header */}
        <div className="case-detail-drawer-header">
          <span className="case-detail-drawer-title">案例详情</span>
          <button
            className="case-detail-drawer-close"
            onClick={onClose}
            type="button"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Body - Left/Right split */}
        <div className="case-detail-drawer-body">
          {/* Left: Data table */}
          <div className="case-detail-drawer-table-panel">
            <div className="case-detail-drawer-table-title">
              {caseData?.tableTitle || '他行存款到期潜力客户名单'}
            </div>
            <table className="case-detail-drawer-table">
              <thead>
                <tr>
                  {tableHeaders.map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => (
                      <td key={j}>{cell}</td>
                    ))}
                    <td>
                      <span className="case-detail-drawer-table-action">
                        去电访
                      </span>
                      <span className="case-detail-drawer-table-action">
                        去洞察
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Right: Steps */}
          <div className="case-detail-drawer-steps-panel">
            {steps.map((step, i) => (
              <div key={i} className="case-detail-drawer-step">
                <div className="case-detail-drawer-step-title">
                  {step.title}
                </div>
                <div className="case-detail-drawer-step-content">
                  {step.content}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="case-detail-drawer-footer">
          <button
            className="case-detail-drawer-footer-btn"
            type="button"
            onClick={() => {
              /* TODO: subscribe as scheduled task */
            }}
          >
            <SubscribeIcon />
            订阅为定时任务
          </button>
          <button
            className="case-detail-drawer-footer-btn case-detail-drawer-footer-btn--primary"
            type="button"
            onClick={handleMakeSimilar}
          >
            <NewSessionIcon />
            做同款
          </button>
        </div>
      </Drawer>
    </>
  );
}
