import React from 'react';
import { AlertTriangle, ShieldCheck, Activity, Flame, Radio, Crosshair } from 'lucide-react';
import { StatisticsSummary } from '../types';

interface StatisticsCardsProps {
  statistics?: StatisticsSummary;
  stats?: StatisticsSummary;
}

export const StatisticsCards: React.FC<StatisticsCardsProps> = ({ statistics, stats }) => {
  const data: StatisticsSummary = statistics || stats || {
    totalEvents: 0,
    criticalEvents: 0,
    highSeverityEvents: 0,
    verifiedEvents: 0,
    potholesDetected: 0,
    trafficSignalsOperating: 0,
    trafficSignalsMalfunction: 0,
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', padding: '12px 16px' }}>
      
      {/* Total Issues */}
      <div className="glass-panel" style={{ padding: '12px 16px', borderLeft: '4px solid var(--accent-blue)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600 }}>TOTAL ISSUES</span>
          <Activity size={16} color="var(--accent-blue)" />
        </div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px' }}>{data.totalEvents}</div>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Geo-tagged Telemetry</span>
      </div>

      {/* Critical Issues */}
      <div className="glass-panel" style={{ padding: '12px 16px', borderLeft: '4px solid var(--severity-critical)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.75rem', color: '#fca5a5', fontWeight: 600 }}>CRITICAL ISSUES</span>
          <Flame size={16} color="var(--severity-critical)" />
        </div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: '#fca5a5' }}>{data.criticalEvents}</div>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Immediate Action</span>
      </div>

      {/* High Priority */}
      <div className="glass-panel" style={{ padding: '12px 16px', borderLeft: '4px solid var(--severity-high)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.75rem', color: '#fdba74', fontWeight: 600 }}>HIGH SEVERITY</span>
          <AlertTriangle size={16} color="var(--severity-high)" />
        </div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: '#fdba74' }}>{data.highSeverityEvents}</div>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>High Priority Queue</span>
      </div>

      {/* Verified Issues */}
      <div className="glass-panel" style={{ padding: '12px 16px', borderLeft: '4px solid var(--status-verified)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.75rem', color: '#93c5fd', fontWeight: 600 }}>VERIFIED (MULTI-BUS)</span>
          <ShieldCheck size={16} color="var(--status-verified)" />
        </div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: '#93c5fd' }}>{data.verifiedEvents}</div>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Multi-Bus Corroborated</span>
      </div>

      {/* Potholes Detected */}
      <div className="glass-panel" style={{ padding: '12px 16px', borderLeft: '4px solid #f59e0b' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.75rem', color: '#fde047', fontWeight: 600 }}>POTHOLES</span>
          <Crosshair size={16} color="#f59e0b" />
        </div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: '#fde047' }}>{data.potholesDetected}</div>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Road Surface Defects</span>
      </div>

      {/* Traffic Signals */}
      <div className="glass-panel" style={{ padding: '12px 16px', borderLeft: '4px solid #06b6d4' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '0.75rem', color: '#67e8f9', fontWeight: 600 }}>TRAFFIC SIGNALS</span>
          <Radio size={16} color="#06b6d4" />
        </div>
        <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: '4px', color: '#67e8f9' }}>
          {data.trafficSignalsOperating + data.trafficSignalsMalfunction}
        </div>
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          {data.trafficSignalsMalfunction > 0 ? `${data.trafficSignalsMalfunction} Possible Malfunction` : 'All Operating'}
        </span>
      </div>

    </div>
  );
};
