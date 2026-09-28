import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { FilterSidebar } from '../components/FilterSidebar';
import { EventFilterState } from '../types';

describe('FilterSidebar Component', () => {
  const initialFilters: EventFilterState = {
    eventType: 'ALL',
    severity: 'ALL',
    lifecycleStatus: 'ALL',
    busId: 'ALL',
    searchQuery: '',
  };

  it('renders filter form controls properly', () => {
    const handleFilterChange = vi.fn();
    const handleReset = vi.fn();

    render(
      <FilterSidebar
        filters={initialFilters}
        onFilterChange={handleFilterChange}
        onResetFilters={handleReset}
        uniqueBusIds={['BUS-001', 'BUS-002']}
        totalCount={10}
        filteredCount={10}
      />
    );

    expect(screen.getByLabelText(/Event Type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Severity Level/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Lifecycle Status/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Vehicle \/ Bus ID/i)).toBeInTheDocument();
  });

  it('triggers onResetFilters when reset button is clicked', () => {
    const handleFilterChange = vi.fn();
    const handleReset = vi.fn();

    render(
      <FilterSidebar
        filters={initialFilters}
        onFilterChange={handleFilterChange}
        onResetFilters={handleReset}
        uniqueBusIds={['BUS-001']}
        totalCount={10}
        filteredCount={5}
      />
    );

    const resetButton = screen.getByRole('button', { name: /reset all filters/i });
    fireEvent.click(resetButton);

    expect(handleReset).toHaveBeenCalledTimes(1);
  });
});
