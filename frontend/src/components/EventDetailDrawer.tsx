import React from 'react';
import { TelemetryEvent } from '../types';
import { StatusBadge, SeverityBadge } from './StatusBadge';

interface EventDetailDrawerProps {
  event: TelemetryEvent | null;
  onClose: () => void;
  onOpenStatusModal: (event: TelemetryEvent) => void;
}

export const EventDetailDrawer: React.FC<EventDetailDrawerProps> = ({
  event,
  onClose,
  onOpenStatusModal,
}) => {
  if (!event) return null;

  const parseMetadata = (metadata: any): Record<string, any> => {
    if (!metadata) return {};
    if (typeof metadata === 'object') return metadata;
    try {
      return JSON.parse(metadata);
    } catch {
      return { raw: metadata };
    }
  };

  const parsedMeta = parseMetadata(event.metadata);

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
    <div className="event-detail-drawer" data-testid="event-detail-drawer">
      <div className="drawer-header">
        <div className="drawer-title-group">
          <span className="event-type-icon">{getEventIcon(event.eventType)}</span>
          <div>
            <h3 className="drawer-title">{event.eventType.replace('_', ' ')}</h3>
            <span className="drawer-subtitle">ID: {event.eventId}</span>
          </div>
        </div>
        <button className="close-btn" onClick={onClose} aria-label="Close drawer">
          &times;
        </button>
      </div>

      <div className="drawer-body">
        {/* Status badges */}
        <div className="drawer-section badges-section">
          <SeverityBadge severity={event.severity} />
          <StatusBadge status={event.lifecycleStatus} />
        </div>

        {/* Multi-bus corroboration indicator */}
        <div className="corroboration-banner" data-testid="observation-count-badge">
          <span className="corroboration-icon">🚌</span>
          <div className="corroboration-text">
            <strong>Observations: {event.observationCount} bus{event.observationCount > 1 ? 'es' : ''}</strong>
            <p className="corroboration-desc">
              {event.observationCount > 1
                ? 'Multi-bus spatial corroboration confirmed'
                : 'Single bus observation logged'}
            </p>
          </div>
        </div>

        {/* Primary Details Grid */}
        <div className="drawer-section">
          <h4 className="section-title">Incident Details</h4>
          <div className="details-grid">
            <div className="detail-item">
              <span className="detail-label">Vehicle ID</span>
              <span className="detail-value font-mono">{event.busId}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Detection Status</span>
              <span className="detail-value">{event.detectionStatus}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">AI Confidence</span>
              <span className="detail-value">{(event.confidence * 100).toFixed(1)}%</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Timestamp</span>
              <span className="detail-value">
                {new Date(event.timestamp).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Spatial / Telemetry Grid */}
        <div className="drawer-section">
          <h4 className="section-title">GIS Telemetry</h4>
          <div className="details-grid">
            <div className="detail-item">
              <span className="detail-label">Latitude</span>
              <span className="detail-value font-mono">
                {event.latitude !== null ? event.latitude.toFixed(6) : 'N/A'}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Longitude</span>
              <span className="detail-value font-mono">
                {event.longitude !== null ? event.longitude.toFixed(6) : 'N/A'}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">GPS Fix Status</span>
              <span className="detail-value">
                <span
                  className={`gps-pill ${
                    event.gpsFixStatus === 'FIX_3D' || event.gpsFixStatus === 'FIX_2D'
                      ? 'gps-valid'
                      : 'gps-invalid'
                  }`}
                >
                  {event.gpsFixStatus}
                </span>
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Source Layer</span>
              <span className="detail-value">{event.source}</span>
            </div>
          </div>
        </div>

        {/* Type-Specific / Metadata Info */}
        {Object.keys(parsedMeta).length > 0 && (
          <div className="drawer-section">
            <h4 className="section-title">Extended Metadata</h4>
            <div className="metadata-container font-mono">
              {Object.entries(parsedMeta).map(([key, val]) => (
                <div key={key} className="meta-row">
                  <span className="meta-key">{key}:</span>
                  <span className="meta-val">
                    {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="drawer-footer">
        <button
          className="btn btn-primary btn-block"
          onClick={() => onOpenStatusModal(event)}
        >
          Update Lifecycle Status
        </button>
      </div>
    </div>
  );
};
