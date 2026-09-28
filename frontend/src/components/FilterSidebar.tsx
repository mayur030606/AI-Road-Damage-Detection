import React from 'react';
import { Filter, Search, RotateCcw } from 'lucide-react';
import { EventFilterState } from '../types';

interface FilterSidebarProps {
  filters: EventFilterState;
  onFilterChange?: (newFilters: EventFilterState) => void;
  onChange?: (newFilters: EventFilterState) => void;
  onResetFilters?: () => void;
  onReset?: () => void;
  uniqueBusIds?: string[];
  busIds?: string[];
  totalCount?: number;
  filteredCount?: number;
}

export const FilterSidebar: React.FC<FilterSidebarProps> = ({
  filters,
  onFilterChange,
  onChange,
  onResetFilters,
  onReset,
  uniqueBusIds,
  busIds: propBusIds,
  totalCount,
  filteredCount,
}) => {
  const handleFilter = onFilterChange || onChange || (() => {});
  const handleReset = onResetFilters || onReset || (() => {});
  const busList = uniqueBusIds || propBusIds || [];

  const handleChange = (field: keyof EventFilterState, value: string) => {
    handleFilter({
      ...filters,
      [field]: value,
    });
  };

  return (
    <aside className="glass-panel" data-testid="filter-sidebar" style={{ width: '280px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px', height: '100%', overflowY: 'auto' }}>
      
      {/* Sidebar Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--panel-border)', paddingBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '0.95rem' }}>
          <Filter size={18} color="var(--accent-cyan)" />
          <span>Filter Telemetry</span>
        </div>
        <button
          onClick={handleReset}
          aria-label="Reset all filters"
          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}
        >
          <RotateCcw size={12} />
          <span>Reset</span>
        </button>
      </div>

      {totalCount !== undefined && filteredCount !== undefined && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          Showing <strong>{filteredCount}</strong> of <strong>{totalCount}</strong> events
        </div>
      )}

      {/* Search Input */}
      <div style={{ position: 'relative' }}>
        <Search size={14} color="var(--text-muted)" style={{ position: 'absolute', left: '10px', top: '10px' }} />
        <input
          type="text"
          placeholder="Search Event ID, Bus ID..."
          aria-label="Search Event ID, Bus ID"
          value={filters.searchQuery}
          onChange={(e) => handleChange('searchQuery', e.target.value)}
          style={{
            width: '100%',
            padding: '8px 10px 8px 30px',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid var(--panel-border)',
            borderRadius: '6px',
            color: 'var(--text-main)',
            fontSize: '0.8rem',
            outline: 'none'
          }}
        />
      </div>

      {/* Event Type Filter */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <label htmlFor="filter-event-type" style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Event Type</label>
        <select
          id="filter-event-type"
          aria-label="Event Type"
          value={filters.eventType}
          onChange={(e) => handleChange('eventType', e.target.value)}
          style={{
            width: '100%',
            padding: '8px',
            background: '#1f2937',
            border: '1px solid var(--panel-border)',
            borderRadius: '6px',
            color: 'var(--text-main)',
            fontSize: '0.85rem'
          }}
        >
          <option value="ALL">All Event Types (4 Modules)</option>
          <option value="POTHOLE">🕳️ Pothole Detection</option>
          <option value="ZEBRA_CROSSING">𚸠 Zebra Crossing Issue</option>
          <option value="TRAFFIC_DENSITY">🚗 Traffic Density</option>
          <option value="TRAFFIC_SIGNAL">🚦 Traffic Signal Intelligence</option>
        </select>
      </div>

      {/* Severity Filter */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <label htmlFor="filter-severity" style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Severity Level</label>
        <select
          id="filter-severity"
          aria-label="Severity Level"
          value={filters.severity}
          onChange={(e) => handleChange('severity', e.target.value)}
          style={{
            width: '100%',
            padding: '8px',
            background: '#1f2937',
            border: '1px solid var(--panel-border)',
            borderRadius: '6px',
            color: 'var(--text-main)',
            fontSize: '0.85rem'
          }}
        >
          <option value="ALL">All Severity Levels</option>
          <option value="CRITICAL">🔥 CRITICAL</option>
          <option value="HIGH">⚠️ HIGH</option>
          <option value="MEDIUM">⚡ MEDIUM</option>
          <option value="LOW">🟢 LOW</option>
          <option value="INFO">ℹ️ INFO</option>
        </select>
      </div>

      {/* Lifecycle Status Filter */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <label htmlFor="filter-lifecycle" style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Lifecycle Status</label>
        <select
          id="filter-lifecycle"
          aria-label="Lifecycle Status"
          value={filters.lifecycleStatus}
          onChange={(e) => handleChange('lifecycleStatus', e.target.value)}
          style={{
            width: '100%',
            padding: '8px',
            background: '#1f2937',
            border: '1px solid var(--panel-border)',
            borderRadius: '6px',
            color: 'var(--text-main)',
            fontSize: '0.85rem'
          }}
        >
          <option value="ALL">All Lifecycle Statuses</option>
          <option value="DETECTED">DETECTED</option>
          <option value="VERIFIED">VERIFIED (Multi-Bus)</option>
          <option value="ASSIGNED">ASSIGNED</option>
          <option value="IN_PROGRESS">IN PROGRESS</option>
          <option value="RESOLVED">RESOLVED</option>
        </select>
      </div>

      {/* Bus ID Filter */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <label htmlFor="filter-bus-id" style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Vehicle / Bus ID</label>
        <select
          id="filter-bus-id"
          aria-label="Vehicle / Bus ID"
          value={filters.busId}
          onChange={(e) => handleChange('busId', e.target.value)}
          style={{
            width: '100%',
            padding: '8px',
            background: '#1f2937',
            border: '1px solid var(--panel-border)',
            borderRadius: '6px',
            color: 'var(--text-main)',
            fontSize: '0.85rem'
          }}
        >
          <option value="ALL">All Fleet Buses</option>
          {busList.map((bus) => (
            <option key={bus} value={bus}>{bus}</option>
          ))}
        </select>
      </div>

    </aside>
  );
};
