"use client";

interface LoadingOverlayProps {
  coords: { lat: number; lng: number } | null;
}

const AGENT_STEPS = [
  { emoji: "🌊", label: "Flood & Water", delay: 0 },
  { emoji: "🌿", label: "Nature & Environment", delay: 200 },
  { emoji: "🏛️", label: "Heritage / Monuments", delay: 400 },
  { emoji: "📐", label: "Zoning & Land Use", delay: 600 },
  { emoji: "⚡", label: "Infrastructure", delay: 800 },
  { emoji: "🤖", label: "Generating Report", delay: 1200 },
];

export function LoadingOverlay({ coords }: LoadingOverlayProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8">
      {/* Animated scanner */}
      <div className="relative w-24 h-24 mb-6">
        <div className="absolute inset-0 rounded-full border-4 border-blue-200 animate-ping opacity-30" />
        <div className="absolute inset-2 rounded-full border-4 border-blue-300 animate-ping opacity-40" style={{ animationDelay: "300ms" }} />
        <div className="absolute inset-4 rounded-full border-4 border-blue-400 animate-pulse" />
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-3xl">🔍</span>
        </div>
      </div>

      <h3 className="text-lg font-bold text-gray-900 mb-1">
        Analyzing Site
      </h3>
      {coords && (
        <p className="text-sm text-gray-500 mb-6">
          {coords.lat.toFixed(4)}, {coords.lng.toFixed(4)}
        </p>
      )}

      {/* Agent progress indicators */}
      <div className="space-y-2 w-full max-w-xs">
        {AGENT_STEPS.map((step, i) => (
          <div
            key={i}
            className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-50 animate-risk-pulse"
            style={{ animationDelay: `${step.delay}ms` }}
          >
            <span className="text-base">{step.emoji}</span>
            <span className="text-sm text-gray-600">{step.label}</span>
            <div className="ml-auto">
              <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-400 mt-6">
        Querying WMS services & generating report…
      </p>
    </div>
  );
}
