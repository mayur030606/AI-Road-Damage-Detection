package com.sih26124.backend.repository;

import com.sih26124.backend.model.EventLifecycleStatus;
import com.sih26124.backend.model.EventSeverity;
import com.sih26124.backend.model.TelemetryEventEntity;
import org.locationtech.jts.geom.Point;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface TelemetryEventRepository extends JpaRepository<TelemetryEventEntity, String> {

    List<TelemetryEventEntity> findByEventType(String eventType);

    List<TelemetryEventEntity> findBySeverity(EventSeverity severity);

    List<TelemetryEventEntity> findByLifecycleStatus(EventLifecycleStatus status);

    List<TelemetryEventEntity> findByBusId(String busId);

    @Query(value = "SELECT * FROM telemetry_events e WHERE e.latitude BETWEEN :minLat AND :maxLat AND e.longitude BETWEEN :minLon AND :maxLon", nativeQuery = true)
    List<TelemetryEventEntity> findWithinBoundingBox(
            @Param("minLat") double minLat,
            @Param("minLon") double minLon,
            @Param("maxLat") double maxLat,
            @Param("maxLon") double maxLon
    );

    @Query(value = "SELECT * FROM telemetry_events e WHERE e.location IS NOT NULL AND ST_DWithin(e.location\\:\\:geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)\\:\\:geography, :radiusMeters) = true ORDER BY ST_Distance(e.location\\:\\:geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)\\:\\:geography) ASC", nativeQuery = true)
    List<TelemetryEventEntity> findNearbyNative(
            @Param("lat") double lat,
            @Param("lon") double lon,
            @Param("radiusMeters") double radiusMeters
    );

    @Query(value = "SELECT * FROM telemetry_events e WHERE e.event_type = :eventType AND e.location IS NOT NULL AND ST_DWithin(e.location\\:\\:geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)\\:\\:geography, :radiusMeters) = true", nativeQuery = true)
    List<TelemetryEventEntity> findCandidatesForCorroborationNative(
            @Param("eventType") String eventType,
            @Param("lat") double lat,
            @Param("lon") double lon,
            @Param("radiusMeters") double radiusMeters
    );
}
