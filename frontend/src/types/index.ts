export type EventLifecycleStatus = 'DETECTED' | 'VERIFIED' | 'ASSIGNED' | 'IN_PROGRESS' | 'RESOLVED';

export type EventSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'INFO';

export interface TelemetryEvent {
  eventId: string;
  busId: string;
  eventType: string; // 'POTHOLE', 'ZEBRA_CROSSING', 'TRAFFIC_DENSITY', 'TRAFFIC_SIGNAL'
  detectionStatus: string;
  confidence: number;
  latitude: number | null;
  longitude: number | null;
  gpsFixStatus: string;
  timestamp: string;
  boundingBox?: string | number[] | null;
  severity: EventSeverity;
  source: string;
  metadata?: string | Record<string, any>;
  lifecycleStatus: EventLifecycleStatus;
  observationCount: number;
  createdAt?: string;
}

export interface EventFilterState {
  eventType: string;
  severity: string;
  lifecycleStatus: string;
  busId: string;
  searchQuery: string;
}

export interface StatisticsSummary {
  totalEvents: number;
  criticalEvents: number;
  highSeverityEvents: number;
  verifiedEvents: number;
  potholesDetected: number;
  trafficSignalsOperating: number;
  trafficSignalsMalfunction: number;
}
