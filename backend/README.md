# SIH26124 Spatial Backend Service

Spring Boot REST API & PostgreSQL / PostGIS Spatial Database for **SIH26124** (Public Transport Sensing Platform).

---

## 🏗️ Backend Stack & Architecture

- **Core Framework**: Java 17, Spring Boot 3.2.3 (REST Web, Spring Data JPA)
- **Spatial Database**: PostgreSQL 15 + PostGIS extension (`Geometry(Point, 4326)`)
- **Spatial Engine**: Hibernate Spatial + LocationTech JTS (`org.locationtech.jts.geom.Point`)
- **Testing**: H2 Database, Mockito, Spring Boot Test

---

## 📡 REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/events` | Ingest `UnifiedTelemetryEvent` payload from bus edge unit. |
| `GET` | `/api/events` | List all events. Optional query filters: `type`, `status`, `severity`. |
| `GET` | `/api/events/{id}` | Get telemetry event by UUID. |
| `GET` | `/api/events/nearby` | PostGIS spatial radius query (`latitude`, `longitude`, `radiusMeters`). |
| `PATCH` | `/api/events/{id}/status` | Update road issue lifecycle status (`DETECTED`, `VERIFIED`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`). |

---

## 🚀 How to Run Locally

### 1. Start PostgreSQL + PostGIS via Docker
```bash
docker-compose up -d
```
Starts container `sih26124_postgis` listening on port `5432`.

### 2. Environment Variables
- `SPRING_DATASOURCE_URL`: `jdbc:postgresql://localhost:5432/sih26124` (Default)
- `SPRING_DATASOURCE_USERNAME`: `postgres` (Default)
- `SPRING_DATASOURCE_PASSWORD`: `postgrespassword` (Default)

### 3. Build & Run Spring Boot App
```bash
cd backend
mvn spring-boot:run
```

### 4. Run Unit Tests
```bash
cd backend
mvn test
```

---

## 🗺️ Multi-Bus Corroboration & Lifecycle

1. **Multi-Bus Matching**: When Bus B reports a pothole within 15 meters of an existing pothole reported by Bus A, `MultiBusCorroborationService` matches the spatial coordinates (`ST_DWithin`), increments observation count, and transitions lifecycle status from `DETECTED` to `VERIFIED`.
2. **Lifecycle Flow**: `DETECTED` $\rightarrow$ `VERIFIED` $\rightarrow$ `ASSIGNED` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `RESOLVED`.
