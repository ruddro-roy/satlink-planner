import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FiGlobe, FiSatellite, FiSettings, FiActivity, FiClock, FiMapPin } from 'react-icons/fi';
import LocationPicker from './components/LocationPicker';
import PassForm from './components/PassForm';
import SatelliteVisualization from './components/SatelliteVisualization';

const NavItem = ({ icon: Icon, label, active, onClick }) => (
  <motion.button
    onClick={onClick}
    className={`flex items-center px-4 py-3 rounded-lg transition-colors ${
      active ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'
    }`}
    whileHover={{ scale: 1.02 }}
    whileTap={{ scale: 0.98 }}
  >
    <Icon className="w-5 h-5 mr-3" />
    <span className="font-medium">{label}</span>
  </motion.button>
);

const StatCard = ({ icon: Icon, title, value, trend }) => (
  <motion.div 
    className="bg-white rounded-xl p-4 shadow-sm border border-gray-100"
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.3 }}
  >
    <div className="flex items-center justify-between">
      <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
        <Icon className="w-5 h-5" />
      </div>
      <span className={`text-xs font-medium px-2 py-1 rounded-full ${
        trend > 0 ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'
      }`}>
        {trend > 0 ? `+${trend}%` : `${trend}%`}
      </span>
    </div>
    <h3 className="mt-4 text-sm text-gray-500">{title}</h3>
    <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
  </motion.div>
);

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedSatellite, setSelectedSatellite] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Simulate loading data
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsLoading(false);
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  const handleSatelliteSelect = (satellite) => {
    setSelectedSatellite(satellite);
  };

  const navItems = [
    { id: 'dashboard', icon: FiActivity, label: 'Dashboard' },
    { id: 'orbits', icon: FiGlobe, label: 'Orbit Visualization' },
    { id: 'passes', icon: FiClock, label: 'Pass Planning' },
    { id: 'locations', icon: FiMapPin, label: 'Locations' },
    { id: 'settings', icon: FiSettings, label: 'Settings' },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-white shadow-lg hidden md:flex flex-col">
        <div className="p-6">
          <div className="flex items-center space-x-2">
            <FiSatellite className="w-8 h-8 text-blue-600" />
            <h1 className="text-xl font-bold text-gray-900">SatLink Pro</h1>
          </div>
          <p className="mt-1 text-xs text-gray-500">Satellite Operations Platform</p>
        </div>
        
        <nav className="flex-1 px-3 space-y-1">
          {navItems.map((item) => (
            <NavItem
              key={item.id}
              icon={item.icon}
              label={item.label}
              active={activeTab === item.id}
              onClick={() => setActiveTab(item.id)}
            />
          ))}
        </nav>
        
        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
              <span className="font-medium text-sm">RR</span>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">Ruddro Roy</p>
              <p className="text-xs text-gray-500">Satellite Engineer</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white shadow-sm z-10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">
              {navItems.find(item => item.id === activeTab)?.label}
            </h1>
            <div className="flex items-center space-x-4">
              <a 
                href="https://celestrak.org" 
                target="_blank" 
                rel="noreferrer"
                className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                <FiGlobe className="mr-2 h-4 w-4" />
                TLE via Celestrak
              </a>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 bg-gray-50">
          <AnimatePresence mode="wait">
            {isLoading ? (
              <div className="flex items-center justify-center h-64">
                <div className="animate-pulse flex flex-col items-center">
                  <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                  <p className="mt-4 text-gray-600">Initializing satellite data...</p>
                </div>
              </div>
            ) : (
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
                className="space-y-6"
              >
                {activeTab === 'dashboard' && (
                  <DashboardView 
                    onSatelliteSelect={handleSatelliteSelect} 
                    selectedSatellite={selectedSatellite} 
                  />
                )}

                {activeTab === 'orbits' && (
                  <div className="bg-white rounded-xl shadow-sm overflow-hidden border border-gray-100 p-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">Interactive Orbit Visualization</h2>
                    <div className="h-[600px] rounded-lg overflow-hidden bg-gray-900">
                      <SatelliteVisualization onSatelliteSelect={handleSatelliteSelect} />
                    </div>
                  </div>
                )}

                {activeTab === 'passes' && <PassPlanningView />}
                {activeTab === 'locations' && <LocationsView />}
                {activeTab === 'settings' && <SettingsView />}
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}

// View Components
const DashboardView = ({ onSatelliteSelect, selectedSatellite }) => (
  <>
    {/* Stats Overview */}
    <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard 
        icon={FiSatellite} 
        title="Active Satellites" 
        value="1,248" 
        trend={2.5} 
      />
      <StatCard 
        icon={FiGlobe} 
        title="Ground Stations" 
        value="87" 
        trend={5.2} 
      />
      <StatCard 
        icon={FiActivity} 
        title="Daily Passes" 
        value="3,542" 
        trend={-1.2} 
      />
      <StatCard 
        icon={FiClock} 
        title="Uptime" 
        value="99.98%" 
        trend={0.1} 
      />
    </div>

    {/* Main Visualization */}
    <div className="bg-white rounded-xl shadow-sm overflow-hidden border border-gray-100">
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Satellite Network Overview</h2>
          <div className="flex space-x-2">
            <button className="px-3 py-1 text-sm font-medium rounded-md bg-blue-50 text-blue-600">
              Real-time
            </button>
            <button className="px-3 py-1 text-sm font-medium rounded-md text-gray-600 hover:bg-gray-50">
              Historical
            </button>
          </div>
        </div>
        <div className="h-[500px] rounded-lg overflow-hidden bg-gray-900">
          <SatelliteVisualization onSatelliteSelect={onSatelliteSelect} />
        </div>
        {selectedSatellite && (
          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <h3 className="font-medium text-blue-800">Selected: {selectedSatellite.name}</h3>
            <div className="mt-2 grid grid-cols-3 gap-4 text-sm text-blue-700">
              <div>
                <p className="text-xs text-blue-500">Altitude</p>
                <p>550 km</p>
              </div>
              <div>
                <p className="text-xs text-blue-500">Inclination</p>
                <p>53°</p>
              </div>
              <div>
                <p className="text-xs text-blue-500">Period</p>
                <p>95.7 min</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  </>
);

const PassPlanningView = () => (
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
    <div className="lg:col-span-1">
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Plan Passes</h2>
        <PassForm />
      </div>
    </div>
    <div className="lg:col-span-2">
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Upcoming Passes</h2>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="p-4 border border-gray-100 rounded-lg hover:bg-gray-50 transition-colors">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium">Starlink-{i * 1000}</h3>
                  <p className="text-sm text-gray-500">AOS: 2025-08-14 1{i}:30:00 UTC</p>
                </div>
                <div className="text-right">
                  <p className="font-medium">+{i * 2} min</p>
                  <p className="text-sm text-gray-500">Max Elev: {70 + i * 5}°</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  </div>
);

const LocationsView = () => (
  <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
    <h2 className="text-lg font-semibold text-gray-900 mb-4">Ground Stations</h2>
    <LocationPicker />
  </div>
);

const SettingsView = () => (
  <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
    <h2 className="text-lg font-semibold text-gray-900 mb-6">Settings</h2>
    <div className="space-y-6 max-w-2xl">
      <div>
        <h3 className="text-sm font-medium text-gray-900 mb-2">API Configuration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">API Endpoint</label>
            <input 
              type="text" 
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
              defaultValue="https://api.satlink.space/v1"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
            <div className="relative">
              <input 
                type="password" 
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                defaultValue="••••••••••••••••"
              />
              <button className="absolute inset-y-0 right-0 pr-3 flex items-center text-sm text-blue-600 hover:text-blue-800">
                Show
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);
