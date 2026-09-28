import { EventFilterState, EventLifecycleStatus, TelemetryEvent } from '../types';
import { DEMO_EVENTS } from './demoData';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api';

export class ApiService {
  private static useDemoMode = false;

  static setDemoMode(enable: boolean) {
    this.useDemoMode = enable;
  }

  static isDemoMode(): boolean {
    return this.useDemoMode;
  }

  static async fetchEvents(filters?: EventFilterState): Promise<{ events: TelemetryEvent[]; isDemoData: boolean }> {
    if (this.useDemoMode) {
      return { events: this.filterDemoEvents(filters), isDemoData: true };
    }

    try {
      const queryParams = new URLSearchParams();
      if (filters?.eventType && filters.eventType !== 'ALL') {
        queryParams.append('type', filters.eventType);
      }
      if (filters?.severity && filters.severity !== 'ALL') {
        queryParams.append('severity', filters.severity);
      }
      if (filters?.lifecycleStatus && filters.lifecycleStatus !== 'ALL') {
        queryParams.append('status', filters.lifecycleStatus);
      }

      const url = `${BASE_URL}/events${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const events: TelemetryEvent[] = await response.json();
      return { events: this.filterClientSide(events, filters), isDemoData: false };
    } catch (error) {
      console.warn('Backend server connection unavailable. Falling back to Demo Mode:', error);
      return { events: this.filterDemoEvents(filters), isDemoData: true };
    }
  }

  static async fetchNearbyEvents(lat: number, lon: number, radiusMeters = 1000): Promise<{ events: TelemetryEvent[]; isDemoData: boolean }> {
    if (this.useDemoMode) {
      return { events: DEMO_EVENTS, isDemoData: true };
    }

    try {
      const url = `${BASE_URL}/events/nearby?latitude=${lat}&longitude=${lon}&radiusMeters=${radiusMeters}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const events = await response.json();
      return { events, isDemoData: false };
    } catch (error) {
      return { events: DEMO_EVENTS, isDemoData: true };
    }
  }

  static async updateEventStatus(eventId: string, status: EventLifecycleStatus): Promise<TelemetryEvent> {
    if (this.useDemoMode || eventId.startsWith('EVT-DEMO')) {
      const event = DEMO_EVENTS.find((e) => e.eventId === eventId);
      if (event) {
        event.lifecycleStatus = status;
        return { ...event };
      }
      throw new Error('Demo event not found');
    }

    const url = `${BASE_URL}/events/${eventId}/status`;
    const response = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ status }),
    });

    if (!response.ok) {
      throw new Error(`Failed to update status (HTTP ${response.status})`);
    }

    return await response.json();
  }

  private static filterDemoEvents(filters?: EventFilterState): TelemetryEvent[] {
    return this.filterClientSide([...DEMO_EVENTS], filters);
  }

  private static filterClientSide(events: TelemetryEvent[], filters?: EventFilterState): TelemetryEvent[] {
    if (!filters) return events;

    return events.filter((evt) => {
      if (filters.eventType && filters.eventType !== 'ALL' && evt.eventType !== filters.eventType) {
        return false;
      }
      if (filters.severity && filters.severity !== 'ALL' && evt.severity !== filters.severity) {
        return false;
      }
      if (filters.lifecycleStatus && filters.lifecycleStatus !== 'ALL' && evt.lifecycleStatus !== filters.lifecycleStatus) {
        return false;
      }
      if (filters.busId && filters.busId !== 'ALL' && evt.busId !== filters.busId) {
        return false;
      }
      if (filters.searchQuery && filters.searchQuery.trim()) {
        const q = filters.searchQuery.toLowerCase();
        const matchesId = evt.eventId.toLowerCase().includes(q);
        const matchesBus = evt.busId.toLowerCase().includes(q);
        const matchesType = evt.eventType.toLowerCase().includes(q);
        const matchesStatus = evt.detectionStatus.toLowerCase().includes(q);
        if (!matchesId && !matchesBus && !matchesType && !matchesStatus) {
          return false;
        }
      }
      return true;
    });
  }
}

export const apiService = {
  fetchEvents: async (forceDemo = false): Promise<TelemetryEvent[]> => {
    if (forceDemo) ApiService.setDemoMode(true);
    const res = await ApiService.fetchEvents();
    return res.events;
  },
  fetchNearbyEvents: async (lat: number, lon: number, radius = 1000): Promise<TelemetryEvent[]> => {
    const res = await ApiService.fetchNearbyEvents(lat, lon, radius);
    return res.events;
  },
  updateEventStatus: async (eventId: string, status: EventLifecycleStatus): Promise<TelemetryEvent> => {
    return await ApiService.updateEventStatus(eventId, status);
  },
  setDemoMode: (enable: boolean) => ApiService.setDemoMode(enable),
  isDemoMode: () => ApiService.isDemoMode(),
};
