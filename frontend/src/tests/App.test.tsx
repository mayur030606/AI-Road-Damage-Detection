import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import App from '../App';

// Mock react-leaflet to avoid DOM map rendering issues in jsdom environment
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: any) => <div data-testid="mock-map-container">{children}</div>,
  TileLayer: () => <div data-testid="mock-tile-layer" />,
  Marker: ({ children, eventHandlers }: any) => (
    <div
      data-testid="mock-marker"
      onClick={() => eventHandlers?.click && eventHandlers.click()}
    >
      {children}
    </div>
  ),
  Popup: ({ children }: any) => <div data-testid="mock-popup">{children}</div>,
  useMap: () => ({
    setView: vi.fn(),
  }),
}));

describe('Municipal GIS Dashboard (SIH26124)', () => {
  it('renders header, title, and initial KPI cards', async () => {
    render(<App />);

    expect(screen.getByText(/SIH26124/i)).toBeInTheDocument();
    expect(screen.getByText(/Urban Road Intelligence Command Center/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/TOTAL ISSUES/i)).toBeInTheDocument();
      expect(screen.getByText(/CRITICAL ISSUES/i)).toBeInTheDocument();
    });
  });

  it('renders filter sidebar and allows filtering by event type', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('filter-sidebar')).toBeInTheDocument();
    });

    const eventTypeSelect = screen.getByLabelText(/Event Type/i);
    fireEvent.change(eventTypeSelect, { target: { value: 'POTHOLE' } });

    await waitFor(() => {
      expect(eventTypeSelect).toHaveValue('POTHOLE');
    });
  });

  it('toggles demo mode state when toggle button is clicked', async () => {
    render(<App />);

    const demoToggle = screen.getByRole('button', { name: /demo data mode/i });
    expect(demoToggle).toBeInTheDocument();

    fireEvent.click(demoToggle);

    await waitFor(() => {
      expect(screen.getByText(/DEMO MODE ACTIVE/i)).toBeInTheDocument();
    });
  });

  it('displays incident table with observations', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('event-table')).toBeInTheDocument();
      expect(screen.getByText(/Active Incidents & Observations/i)).toBeInTheDocument();
    });
  });
});
