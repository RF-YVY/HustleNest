"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import type { GeographyWorkspaceData } from "../lib/hustlenest";

type Destination = GeographyWorkspaceData["destinations"][number];

export function DestinationDistributionMap({ destinations, selectedKey, onSelect }: { destinations: Destination[]; selectedKey: string | null; onSelect: (key: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const onSelectRef = useRef(onSelect);

  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);

  useEffect(() => {
    let disposed = false;
    void import("leaflet").then((Leaflet) => {
      if (disposed || !containerRef.current) return;
      mapRef.current?.remove();
      const map = Leaflet.map(containerRef.current, { center: [39.5, -98.35], zoom: 4, minZoom: 3, zoomControl: true });
      Leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18,
      }).addTo(map);
      const bounds = Leaflet.latLngBounds([]);
      for (const destination of destinations) {
        if (destination.latitude === null || destination.longitude === null) continue;
        const active = destination.key === selectedKey;
        const marker = Leaflet.circleMarker([destination.latitude, destination.longitude], {
          radius: Math.min(18, 7 + Math.sqrt(destination.count) * 2.5),
          color: active ? "#9a6110" : "#ffffff",
          weight: active ? 4 : 2,
          fillColor: active ? "#e3a12d" : "#238b8f",
          fillOpacity: .9,
        });
        const tooltip = document.createElement("span");
        tooltip.textContent = `${destination.city}, ${destination.state} · ${destination.count} order${destination.count === 1 ? "" : "s"}`;
        marker.bindTooltip(tooltip, { direction: "top", offset: [0, -8] });
        marker.on("click", () => onSelectRef.current(destination.key));
        marker.addTo(map);
        if (active) marker.bringToFront();
        bounds.extend([destination.latitude, destination.longitude]);
      }
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [35, 35], maxZoom: 7 });
      mapRef.current = map;
    });
    return () => { disposed = true; mapRef.current?.remove(); mapRef.current = null; };
  }, [destinations, selectedKey]);

  return <div ref={containerRef} className="leaflet-destination-map" aria-label="Map of all order destinations" />;
}
