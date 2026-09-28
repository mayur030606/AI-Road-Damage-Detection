import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { TelemetryEvent, EventFilterState, StatisticsSummary, EventLifecycleStatus } from './types';
import { apiService } from './services/api';
import { Header } from './components/Header';
import { StatisticsCards } from './components/StatisticsCards';
import { FilterSidebar } from './components/FilterSidebar';
import { EventMap } from './components/EventMap';
import { EventTable } from './components/EventTable';
import { EventDetailDrawer } from './components/EventDetailDrawer';
import { StatusUpdateModal } from './components/StatusUpdateModal';

export const App: React.FC = () => {
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isDemoMode, setIsDemoMode] = useState<boolean>(false);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [selectedEvent, setSelectedEvent] = useState<TelemetryEvent | null>(null);
  const [statusModalEvent, setStatusModalEvent] = useState<TelemetryEvent | null>(null);
  const [isStatusModalOpen, setIsStatusModalOpen] = useState<boolean>(false);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  const [filters, setFilters] = useState<EventFilterState>({
    eventType: 'ALL',
    severity: 'ALL',
    lifecycleStatus: 'ALL',
    busId: 'ALL',
    searchQuery: '',
  });

  // Fetch events from API or fallback
  const loadEvents = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await apiService.fetchEvents(isDemoMode);
      setEvents(data);
      setIsConnected(!isDemoMode);
      setErrorNotice(null);
    } catch (err: any) {
      console.warn('Backend fetch error, activating demo mode fallback:', err);
      setIsConnected(false);
      // Fallback to demo events
      const demoData = await apiService.fetchEvents(true);
      setEvents(demoData);
      setErrorNotice('Live Spring Boot backend disconnected. Displaying [DEMO DATA].');
    } finally {
      setIsLoading(false);
    }
  }, [isDemoMode]);

  useEffect(() => {
    loadEvents();
    // Poll every 15s if not explicitly in demo mode
    const timer = setInterval(() => {
      loadEvents();
    }, 15000);
    return () => clearInterval(timer);
  }, [loadEvents]);

  // Extract unique bus IDs for filter dropdown
  const uniqueBusIds = useMemo(() => {
    const ids = new Set<string>();
    events.forEach((e) => {
      if (e.busId) ids.add(e.busId);
    });
    return Array.from(ids).sort();
  }, [events]);

  // Filter events based on active filter state
  const filteredEvents = useMemo(() => {
    return events.filter((evt) => {
      if (filters.eventType !== 'ALL' && evt.eventType !== filters.eventType) {
        return false;
      }
      if (filters.severity !== 'ALL' && evt.severity !== filters.severity) {
        return false;
      }
      if (filters.lifecycleStatus !== 'ALL' && evt.lifecycleStatus !== filters.lifecycleStatus) {
        return false;
      }
      if (filters.busId !== 'ALL' && evt.busId !== filters.busId) {
        return false;
      }
      if (filters.searchQuery.trim() !== '') {
        const query = filters.searchQuery.toLowerCase();
        const matchesId = evt.eventId.toLowerCase().includes(query);
        const matchesBus = evt.busId.toLowerCase().includes(query);
        const matchesType = evt.eventType.toLowerCase().includes(query);
        const matchesSource = evt.source.toLowerCase().includes(query);
        if (!matchesId && !matchesBus && !matchesType && !matchesSource) {
          return false;
        }
      }
      return true;
    });
  }, [events, filters]);

  // Calculate KPI Statistics
  const statistics = useMemo<StatisticsSummary>(() => {
    let totalEvents = events.length;
    let criticalEvents = 0;
    let highSeverityEvents = 0;
    let verifiedEvents = 0;
    let potholesDetected = 0;
    let trafficSignalsOperating = 0;
    let trafficSignalsMalfunction = 0;

    events.forEach((e) => {
      if (e.severity === 'CRITICAL') criticalEvents++;
      if (e.severity === 'HIGH') highSeverityEvents++;
      if (e.lifecycleStatus === 'VERIFIED') verifiedEvents++;
      if (e.eventType === 'POTHOLE') potholesDetected++;

      if (e.eventType === 'TRAFFIC_SIGNAL') {
        const metaStr = typeof e.metadata === 'object' ? JSON.stringify(e.metadata) : (e.metadata || '');
        if (e.detectionStatus === 'SIGNAL_POSSIBLE_MALFUNCTION' || metaStr.includes('MALFUNCTION')) {
          trafficSignalsMalfunction++;
        } else if (e.detectionStatus === 'SIGNAL_OPERATING' || metaStr.includes('OPERATING')) {
          trafficSignalsOperating++;
        }
      }
    });

    return {
      totalEvents,
      criticalEvents,
      highSeverityEvents,
      verifiedEvents,
      potholesDetected,
      trafficSignalsOperating,
      trafficSignalsMalfunction,
    };
  }, [events]);

  const handleResetFilters = () => {
    setFilters({
      eventType: 'ALL',
      severity: 'ALL',
      lifecycleStatus: 'ALL',
      busId: 'ALL',
      searchQuery: '',
    });
  };

  const handleToggleDemoMode = () => {
    setIsDemoMode((prev) => !prev);
  };

  const handleOpenStatusModal = (evt: TelemetryEvent) => {
    setStatusModalEvent(evt);
    setIsStatusModalOpen(true);
  };

  const handleUpdateStatus = async (eventId: string, newStatus: EventLifecycleStatus) => {
    const updated = await apiService.updateEventStatus(eventId, newStatus);
    setEvents((prev) =>
      prev.map((e) => (e.eventId === eventId ? { ...e, lifecycleStatus: updated.lifecycleStatus } : e))
    );
    if (selectedEvent?.eventId === eventId) {
      setSelectedEvent((prev) => (prev ? { ...prev, lifecycleStatus: updated.lifecycleStatus } : null));
    }
  };

  return (
    <div className="dashboard-app" data-testid="dashboard-app">
      <Header
        isConnected={isConnected}
        isDemoMode={isDemoMode}
        onToggleDemoMode={handleToggleDemoMode}
      />

      <main className="dashboard-content">
        {errorNotice && (
          <div className="notice-banner" data-testid="notice-banner">
            <span className="notice-icon">⚠️</span>
            <span className="notice-text">{errorNotice}</span>
            <button className="notice-close" onClick={() => setErrorNotice(null)}>
              &times;
            </button>
          </div>
        )}

        <StatisticsCards statistics={statistics} />

        <div className="main-workspace-grid">
          <FilterSidebar
            filters={filters}
            onFilterChange={setFilters}
            onResetFilters={handleResetFilters}
            uniqueBusIds={uniqueBusIds}
            totalCount={events.length}
            filteredCount={filteredEvents.length}
          />

          <div className="map-view-column">
            <EventMap
              events={filteredEvents}
              selectedEvent={selectedEvent}
              onSelectEvent={setSelectedEvent}
            />
          </div>
        </div>

        <div className="table-workspace-section">
          <EventTable
            events={filteredEvents}
            selectedEvent={selectedEvent}
            onSelectEvent={setSelectedEvent}
            onOpenStatusModal={handleOpenStatusModal}
          />
        </div>
      </main>

      <EventDetailDrawer
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
        onOpenStatusModal={handleOpenStatusModal}
      />

      <StatusUpdateModal
        event={statusModalEvent}
        isOpen={isStatusModalOpen}
        onClose={() => setIsStatusModalOpen(false)}
        onUpdateStatus={handleUpdateStatus}
      />
    </div>
  );
};

export default App;
