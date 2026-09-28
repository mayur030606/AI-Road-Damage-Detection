import React from 'react';
import { TelemetryEvent } from '../types';
import { StatusBadge, SeverityBadge } from './StatusBadge';

interface EventTableProps {
  events: TelemetryEvent[];
  selectedEvent: TelemetryEvent | null;
  onSelectEvent: (event: TelemetryEvent) => void;
  onOpenStatusModal: (event: TelemetryEvent) => void;
}

export const EventTable: React.FC<EventTableProps> = ({
  events,
  selectedEvent,
  onSelectEvent,
  onOpenStatusModal,
}) => {
  const getEventIcon = (type: string) => {
    switch (type) {
      case 'POTHOLE':
        return '🕳️';
      case 'ZEBRA_CROSSING':
        return '🚸';
      case 'TRAFFIC_DENSITY':
        return '🚗';
      case 'TRAFFIC_SIGNAL':
        return '🚦';
      default:
        return '📍';
    }
  };

  return (
    <div className="event-table-card" data-testid="event-table">
      <div className="table-header">
        <div className="table-title-group">
          <h3 className="table-title">Active Incidents & Observations</h3>
          <span className="table-count-badge">{events.length} Records</span>
        </div>
      </div>

      <div className="table-responsive font-sans">
        {events.length === 0 ? (
          <div className="empty-table-state">
            <span className="empty-icon">🔍</span>
            <p>No incidents match the active filters.</p>
            <span className="empty-subtext">Try adjusting severity, type, or search terms.</span>
          </div>
        ) : (
          <table className="incident-table">
            <thead>
              <tr>
                <th>Event</th>
                <th>Severity</th>
                <th>Lifecycle Status</th>
                <th>Bus ID</th>
                <th>Coordinates (Lat, Lon)</th>
                <th>Corroboration</th>
                <th>Confidence</th>
                <th>Timestamp</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {events.map((evt) => {
                const isSelected = selectedEvent?.eventId === evt.eventId;
                return (
                  <tr
                    key={evt.eventId}
                    className={`table-row ${isSelected ? 'row-selected' : ''}`}
                    onClick={() => onSelectEvent(evt)}
                  >
                    <td>
                      <div className="table-event-cell">
                        <span className="cell-icon">{getEventIcon(evt.eventType)}</span>
                        <div>
                          <div className="event-cell-name">{evt.eventType.replace('_', ' ')}</div>
                          <div className="event-cell-id font-mono">{evt.eventId}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <SeverityBadge severity={evt.severity} />
                    </td>
                    <td>
                      <StatusBadge status={evt.lifecycleStatus} />
                    </td>
                    <td className="font-mono text-sm">{evt.busId}</td>
                    <td className="font-mono text-sm">
                      {evt.latitude !== null && evt.longitude !== null
                        ? `${evt.latitude.toFixed(4)}, ${evt.longitude.toFixed(4)}`
                        : 'No GPS'}
                    </td>
                    <td>
                      <span className="obs-badge" title="Number of bus observations">
                        🚌 {evt.observationCount}
                      </span>
                    </td>
                    <td>
                      <div className="confidence-pill">
                        {(evt.confidence * 100).toFixed(0)}%
                      </div>
                    </td>
                    <td className="text-sm text-muted">
                      {new Date(evt.timestamp).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>
                    <td>
                      <button
                        className="btn btn-sm btn-ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenStatusModal(evt);
                        }}
                      >
                        Update
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
