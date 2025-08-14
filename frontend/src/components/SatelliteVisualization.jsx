import { Canvas } from '@react-three/fiber';
import { OrbitControls, Stars, Line } from '@react-three/drei';
import { useRef, useMemo, useEffect, useState } from 'react';
import * as THREE from 'three';
import { useSpring, animated } from '@react-spring/three';

const Earth = ({ radius = 1 }) => (
  <mesh>
    <sphereGeometry args={[radius, 32, 32]} />
    <meshStandardMaterial 
      color="#1a73e8" 
      metalness={0.4} 
      roughness={0.7}
      emissive="#0d47a1"
      emissiveIntensity={0.1}
    />
  </mesh>
);

const Satellite = ({ position, color = "#ff3d00" }) => {
  const meshRef = useRef();
  
  const { scale } = useSpring({
    from: { scale: 0 },
    to: { scale: 1 },
    config: { mass: 1, tension: 180, friction: 12 }
  });

  return (
    <animated.mesh position={position} scale={scale} ref={meshRef}>
      <sphereGeometry args={[0.05, 16, 16]} />
      <meshStandardMaterial 
        color={color} 
        emissive={color} 
        emissiveIntensity={0.5}
      />
    </animated.mesh>
  );
};

const OrbitPath = ({ points, color = "#ffffff" }) => {
  const lineGeometry = useMemo(() => {
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    geometry.computeBoundingSphere();
    return geometry;
  }, [points]);

  return (
    <line geometry={lineGeometry}>
      <lineBasicMaterial 
        attach="material" 
        color={color} 
        linewidth={1} 
        linecap={'round'}
        linejoin={'round'}
        transparent
        opacity={0.7}
      />
    </line>
  );
};

export const SatelliteVisualization = ({ tleData, selectedSatellite, onSatelliteSelect }) => {
  const [satellites, setSatellites] = useState([]);
  const [orbits, setOrbits] = useState({});
  const controlsRef = useRef();

  // Generate sample satellite data if none provided
  useEffect(() => {
    if (!tleData || tleData.length === 0) {
      // Generate sample satellites if no data provided
      const sampleSatellites = Array(3).fill().map((_, i) => ({
        id: `sat-${i}`,
        name: `Satellite ${i + 1}`,
        position: [
          (Math.random() - 0.5) * 3,
          (Math.random() - 0.5) * 3,
          (Math.random() - 0.5) * 3
        ],
        color: `hsl(${Math.random() * 360}, 70%, 60%)`,
        orbit: Array(100).fill().map((_, i) => {
          const angle = (i / 100) * Math.PI * 2;
          return new THREE.Vector3(
            Math.cos(angle) * (1.5 + Math.random() * 0.5),
            Math.sin(angle * 0.5) * 0.5,
            Math.sin(angle) * (1.5 + Math.random() * 0.5)
          );
        })
      }));
      
      setSatellites(sampleSatellites);
      
      // Auto-select first satellite
      if (sampleSatellites.length > 0) {
        onSatelliteSelect?.(sampleSatellites[0]);
      }
    } else {
      // Process real TLE data here
      // This is a placeholder - implement TLE parsing as needed
      const processed = tleData.map(tle => ({
        id: tle.noradId,
        name: tle.name,
        position: [0, 2, 0], // Placeholder
        color: `hsl(${Math.random() * 360}, 70%, 60%)`,
        orbit: [] // Calculate orbit points from TLE
      }));
      setSatellites(processed);
    }
  }, [tleData]);

  return (
    <div className="w-full h-[600px] bg-gray-900 rounded-xl overflow-hidden">
      <Canvas camera={{ position: [0, 0, 5], fov: 50 }}>
        <ambientLight intensity={0.2} />
        <pointLight position={[10, 10, 10]} intensity={1} />
        <pointLight position={[-10, -10, -10]} intensity={0.5} />
        
        <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />
        
        <Earth radius={1.5} />
        
        {satellites.map((sat) => (
          <group key={sat.id}>
            <Satellite 
              position={sat.position} 
              color={sat.color}
              onClick={() => onSatelliteSelect?.(sat)}
            />
            {sat.orbit && sat.orbit.length > 0 && (
              <OrbitPath points={sat.orbit} color={sat.color} />
            )}
          </group>
        ))}
        
        <OrbitControls 
          ref={controlsRef}
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          minDistance={3}
          maxDistance={20}
        />
      </Canvas>
    </div>
  );
};

export default SatelliteVisualization;
