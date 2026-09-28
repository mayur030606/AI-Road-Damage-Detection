import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { TelemetryEvent } from '../types';

interface EventMapProps {
  events: TelemetryEvent[];
  selectedEvent: TelemetryEvent | null;
  onSelectEvent: (event: TelemetryEvent) => void;
}

// Custom Leaflet Marker Icon Generator
function createCustomIcon(event: TelemetryEvent) {
  let emoji = '📌';
  if (event.eventType === 'POTHOLE') emoji = '🕳️';
  else if (event.eventType === 'ZEBRA_CROSSING') emoji = '🚸';
  else if (event.eventType === 'TRAFFIC_DENSITY') emoji = '🚗';
  else if (event.eventType === 'TRAFFIC_SIGNAL') emoji = '🚦';

  const sevClass = `marker-halo-${event.severity.toLowerCase()}`;

  const html = `
    <div class="custom-leaflet-marker ${sevClass}">
      <span>${emoji}</span>
    </div>
  `;

  return L.divIcon({
    html: html,
    className: '',
    iconSize: [38, 38],
    iconAnchor: [19, 19],
    popupAnchor: [0, -20],
  });
}

// Controller to auto-center map when event selected
function MapRecenter({ selectedEvent }: { selectedEvent: TelemetryEvent | null }) {
  const map = useMap();
  useEffect(() => {
    if (selectedEvent && selectedEvent.latitude && selectedEvent.longitude) {
      map.setView([selectedEvent.latitude, selectedEvent.longitude], 15, { animate: true });
    }
  }, [selectedEvent, map]);
  return null;
}

export const EventMap: React.FC<EventMapProps> = ({ events, selectedEvent, onSelectEvent }) => {
  // Default map center (Pune, India coordinates default)
  const defaultCenter: [number, number] = [18.5204, 73.8567];

  const validEvents = events.filter((e) => e.latitude !== null && e.longitude !== null);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <MapContainer
        center={defaultCenter}
        zoom={13}
        scrollWheelZoom={true}
        style={{ width: '100%', height: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapRecenter selectedEvent={selectedEvent} />

        {validEvents.map((evt) => {
          const position: [number, number] = [evt.latitude!, evt.longitude!];
          const icon = createCustomIcon(evt);

          return (
            <Marker
              key={evt.eventId}
              position={position}
              icon={icon}
              eventHandlers={{
                click: () => onSelectEvent(evt),
              }}
            >
              <Popup className="glass-panel">
                <div style={{ padding: '4px', fontSize: '0.85rem' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.9rem', marginBottom: '4px' }}>
                    {evt.eventType} ({evt.detectionStatus})
                  </div>
                  <div style={{ color: 'var(--text-muted)', marginBottom: '4px' }}>
                    Bus: <strong>{evt.busId}</strong> | Conf: {(evt.confidence * 100).toFixed(0)}%
                  </div>
                  <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                    <span className={`badge badge-${evt.severity.toLowerCase()}`}>{evt.severity}</span>
                    <span className={`badge badge-${evt.lifecycleStatus.toLowerCase()}`}>{evt.lifecycleStatus}</span>
                  </div>
                  {evt.observationCount > 1 && (
                    <div style={{ marginTop: '6px', fontSize: '0.75rem', color: '#93c5fd', fontWeight: 600 }}>
                      Observations: {evt.observationCount} buses
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
};
