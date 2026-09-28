import React from 'react';
import { EventLifecycleStatus, EventSeverity } from '../types';

interface StatusBadgeProps {
  status: EventLifecycleStatus | string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const stat = String(status).toUpperCase() as EventLifecycleStatus;
  const badgeClass =
    stat === 'DETECTED' ? 'badge-detected' :
    stat === 'VERIFIED' ? 'badge-verified' :
    stat === 'ASSIGNED' ? 'badge-assigned' :
    stat === 'IN_PROGRESS' ? 'badge-in-progress' : 'badge-resolved';

  return <span className={`badge ${badgeClass}`}>{stat.replace('_', ' ')}</span>;
};

interface SeverityBadgeProps {
  severity: EventSeverity | string;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity }) => {
  const sev = String(severity).toUpperCase() as EventSeverity;
  const badgeClass =
    sev === 'CRITICAL' ? 'badge-critical' :
    sev === 'HIGH' ? 'badge-high' :
    sev === 'MEDIUM' ? 'badge-medium' :
    sev === 'LOW' ? 'badge-low' : 'badge-info';

  return <span className={`badge ${badgeClass}`}>{sev}</span>;
};
