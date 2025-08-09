"use client";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Stars } from "@react-three/drei";
import type { Object3D } from "three";

type Satellite = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  altKm: number;
};

type Props = {
  satellites: Satellite[];
  ground?: { lat: number; lon: number } | null;
  onSatelliteClick?: (sat: Satellite) => void;
};

type GlobePoint = {
  type: "sat" | "gs";
  id: string;
  name: string;
  lat: number;
  lng: number;
  altKm: number;
  size: number;
  color: string;
};

type ThreeGlobeInstance = Object3D & {
  globeImageUrl: (url: string) => ThreeGlobeInstance;
  bumpImageUrl: (url: string) => ThreeGlobeInstance;
  atmosphereColor: (color: string) => ThreeGlobeInstance;
  atmosphereAltitude: (alt: number) => ThreeGlobeInstance;
  pointsData: (data: GlobePoint[]) => ThreeGlobeInstance;
  pointColor: (key: string | ((d: GlobePoint) => string)) => ThreeGlobeInstance;
  pointAltitude: (fn: (d: GlobePoint) => number) => ThreeGlobeInstance;
  pointRadius: (key: string) => ThreeGlobeInstance;
  onPointClick: (handler: (d: GlobePoint, event: MouseEvent) => void) => ThreeGlobeInstance;
};

function GlobeInner({ satellites, ground, onSatelliteClick }: Props) {
  const globeRef = useRef<Object3D | null>(null);
  const [globe, setGlobe] = useState<ThreeGlobeInstance | null>(null);

  useEffect(() => {
    let mounted = true;
    import("three-globe").then((mod) => {
      if (!mounted) return;
      const Ctor = mod.default as unknown as { new (opts?: Record<string, unknown>): unknown };
      const instance = new Ctor({ waitForGlobeReady: true }) as unknown as ThreeGlobeInstance;
      setGlobe(instance);
    });
    return () => {
      mounted = false;
    };
  }, []);

  useMemo(() => {
    if (!globe) return;
    // Dark theme with blue oceans
    globe
      .globeImageUrl("https://unpkg.com/three-globe/example/img/earth-dark.jpg")
      .bumpImageUrl("https://unpkg.com/three-globe/example/img/earth-topology.png")
      .atmosphereColor("#4ea1ff")
      .atmosphereAltitude(0.2);
  }, [globe]);

  useMemo(() => {
    if (!globe) return;
    const satPoints: GlobePoint[] = satellites.map((s) => ({
      type: "sat",
      id: s.id,
      name: s.name,
      lat: s.lat,
      lng: s.lon,
      altKm: s.altKm,
      size: 0.6,
      color: "#7dd3fc",
    }));
    const groundPoints: GlobePoint[] = ground
      ? [
          {
            type: "gs",
            id: "ground",
            name: "Ground Station",
            lat: ground.lat,
            lng: ground.lon,
            altKm: 0,
            size: 1.2,
            color: "#22d3ee",
          },
        ]
      : [];
    const points: GlobePoint[] = [...satPoints, ...groundPoints];
    globe
      .pointsData(points)
      .pointColor("color")
      .pointAltitude((d: GlobePoint) => (d.type === "sat" ? 0.01 + (d.altKm || 500) / 20000 : 0.01))
      .pointRadius("size");
    globe.onPointClick((d) => {
      if (d.type === "sat" && onSatelliteClick) {
        onSatelliteClick({ id: d.id, name: d.name, lat: d.lat, lon: d.lng, altKm: d.altKm });
      }
    });
  }, [globe, satellites, ground, onSatelliteClick]);

  useFrame(() => {
    if (globeRef.current) {
      globeRef.current.rotation.y += 0.0005;
    }
  });

  if (!globe) return null;
  return <primitive ref={globeRef} object={globe} />;
}

export function Globe3D(props: Props) {
  return (
    <div className="relative h-[60vh] w-full rounded-xl overflow-hidden bg-black/60">
      <Canvas camera={{ position: [0, 0, 350] }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[100, 50, 100]} intensity={1.0} />
        <Suspense fallback={null}>
          <GlobeInner {...props} />
        </Suspense>
        <Stars radius={300} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />
        <OrbitControls enablePan={false} minDistance={200} maxDistance={600} />
      </Canvas>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(56,189,248,0.15),transparent_40%),radial-gradient(circle_at_80%_70%,rgba(99,102,241,0.15),transparent_40%)]" />
    </div>
  );
}


