import React from 'react';
import { Activity, Shield, Database, Sparkles, RefreshCw } from 'lucide-react';

interface HeaderProps {
  isDemoMode?: boolean;
  isConnected?: boolean;
  isDemoData?: boolean;
  onToggleDemoMode?: () => void;
  onRefresh?: () => void;
  isLoading?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  isDemoMode = false,
  isConnected = false,
  isDemoData = false,
  onToggleDemoMode = () => {},
  onRefresh = () => {},
  isLoading = false,
}) => {
  const showDemoData = isDemoMode || isDemoData || !isConnected;

  return (
    <header className="glass-panel" data-testid="header" style={{ borderRadius: 0, borderTop: 0, borderLeft: 0, borderRight: 0, padding: '12px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        
        {/* Brand & Project Identity */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            background: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
            padding: '8px 12px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 0 15px rgba(6, 182, 212, 0.4)'
          }}>
            <Shield size={22} color="#ffffff" />
            <span style={{ fontWeight: 700, fontSize: '1.1rem', letterSpacing: '0.05em' }}>SIH26124</span>
          </div>
          <div>
            <h1 style={{ fontSize: '1.2rem', fontWeight: 700, lineHeight: 1.2 }}>Urban Road Intelligence Command Center</h1>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Public Transport Fleet AI Sensing & PostGIS Spatial Telemetry Platform</p>
          </div>
        </div>

        {/* Live Status Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          
          {/* Data Source Badge */}
          {showDemoData ? (
            <div className="demo-tag animate-pulse-subtle" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Sparkles size={12} />
              <span>{isDemoMode ? 'DEMO MODE ACTIVE' : '[DEMO DATA MODE]'}</span>
            </div>
          ) : (
            <div className="badge badge-low" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Database size={12} />
              <span>POSTGIS BACKEND CONNECTED</span>
            </div>
          )}

          {/* Connection Status Indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            <Activity size={16} color={showDemoData ? '#f59e0b' : '#10b981'} className="animate-pulse-subtle" />
            <span>{showDemoData ? 'Offline Backup' : 'Live Ingestion'}</span>
          </div>

          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            disabled={isLoading}
            aria-label="Refresh data"
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid var(--panel-border)',
              color: 'var(--text-main)',
              padding: '6px 12px',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.8rem',
              transition: 'background 0.2s ease'
            }}
          >
            <RefreshCw size={14} className={isLoading ? 'spin' : ''} />
            <span>Refresh</span>
          </button>

          {/* Demo Toggle Button */}
          <button
            onClick={onToggleDemoMode}
            aria-label="Demo Data Mode"
            style={{
              background: isDemoMode ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255, 255, 255, 0.05)',
              border: isDemoMode ? '1px solid rgba(245, 158, 11, 0.5)' : '1px solid var(--panel-border)',
              color: isDemoMode ? '#fde047' : 'var(--text-muted)',
              padding: '6px 12px',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '0.8rem',
              fontWeight: 600
            }}
          >
            {isDemoMode ? 'Exit Demo Mode' : 'Toggle Demo Mode'}
          </button>

        </div>
      </div>
    </header>
  );
};
