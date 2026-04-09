import { Routes, Route, Navigate } from "react-router-dom";
import OverviewPage from "./Overview";
import InstancesPage from "./Instances";
import AllocationsPage from "./Allocations";
import OperationLogsPage from "./OperationLogs";

export default function InstancePage() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="overview" replace />} />
      <Route path="overview" element={<OverviewPage />} />
      <Route path="instances" element={<InstancesPage />} />
      <Route path="allocations" element={<AllocationsPage />} />
      <Route path="operation-logs" element={<OperationLogsPage />} />
    </Routes>
  );
}
