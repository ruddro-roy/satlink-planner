"use client";

import { useEffect, useRef } from "react";
import { Viewer, Entity, PointGraphics } from "resium";
import { Cartesian3, Color } from "cesium";
import { useRealTimeSatellites, type LiveSatellite } from "../hooks/useRealTimeSatellites";

export default function SatelliteGlobe() {
  const satellites = useRealTimeSatellites();
  const viewerRef = useRef<any>(null);

  useEffect(() => {
    if (viewerRef.current?.cesiumElement) {
      const viewer = viewerRef.current.cesiumElement;
      viewer.scene.globe.enableLighting = true;
    }
  }, []);

  return (
    <Viewer
      ref={viewerRef}
      full
      animation={false}
      timeline={false}
      homeButton={false}
      navigationHelpButton={false}
      sceneModePicker={false}
      baseLayerPicker={false}
    >
      {satellites.map((sat: LiveSatellite) => (
        <Entity
          key={sat.id}
          name={sat.name}
          position={Cartesian3.fromDegrees(sat.lon, sat.lat, sat.altKm * 1000)}
        >
          <PointGraphics pixelSize={10} color={Color.RED} />
        </Entity>
      ))}
    </Viewer>
  );
}
