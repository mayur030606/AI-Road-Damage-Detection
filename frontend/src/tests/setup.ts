import '@testing-library/jest-dom';

// Leaflet mock fix for jsdom
if (typeof window !== 'undefined') {
  window.URL.createObjectURL = window.URL.createObjectURL || (() => 'blob:mock');
}
