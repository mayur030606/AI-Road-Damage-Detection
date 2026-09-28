# SIH26124 - Urban Road Intelligence Municipal GIS Dashboard

The web-based Municipal Command Center for **SIH26124: Automated Urban Infrastructure Monitoring System**.

## 🌟 Capabilities

- **Interactive GIS Map**: React Leaflet GIS map with custom markers (🕳️ Potholes, 🚸 Zebra Crossings, 🚗 Traffic Density, 🚦 Traffic Signals) and pulsing severity halos (Critical, High, Medium, Low, Info).
- **Multi-bus Spatial Corroboration**: Displays `observation_count` badges ("Observations: X buses") reflecting real-time multi-bus evidence aggregation.
- **Traffic Signal Intelligence**: Visualizes signal health and clearly highlights state recognition (`SIGNAL_OPERATING`, `SIGNAL_POSSIBLE_MALFUNCTION`, `SIGNAL_STATE_UNKNOWN`).
- **Multi-Attribute Filters**: Filter incidents dynamically by Event Type, Severity Level, Lifecycle Status, Bus ID, and quick keyword search.
- **Incident Lifecycle Management**: Operator dialog for triggering status changes (`DETECTED`, `VERIFIED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`) via `PATCH /api/events/{id}/status`.
- **Demo / Offline Fallback Mode**: Toggle button to view rich simulated dataset (`[DEMO DATA]`) when backend is disconnected.

## 🚀 Quick Start

### Prerequisites
- Node.js (v18+)
- npm (v9+)

### Installation
```bash
cd frontend
npm install
```

### Environment Setup
Copy `.env.example` to `.env`:
```bash
VITE_API_BASE_URL=http://localhost:8080/api
```

### Running Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### Running Unit Tests
```bash
npm test
```

### Production Build
```bash
npm run build
```

## 🏗️ Technical Stack

- **Framework**: React 18 with TypeScript & Vite
- **Mapping**: Leaflet & React Leaflet
- **Icons**: Lucide React
- **Testing**: Vitest & React Testing Library
- **Design System**: Vanilla CSS Glassmorphism Dark Mode with CSS Grid/Flexbox
