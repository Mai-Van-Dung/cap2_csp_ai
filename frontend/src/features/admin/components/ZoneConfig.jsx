import { Minus, Pencil, Plus, Trash2, TriangleAlert } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'

const LIVE_STREAM_URL = 'http://localhost:5000/video_feed'

const GAUGE_ARC = 157.08
const clamp01 = (n) => Math.max(0, Math.min(1, n))

const createDefaultZones = () => [
  {
    id: 'DPZ-01',
    name: 'Pool Perimeter',
    vertices: [
      { x: 0.18, y: 0.57 },
      { x: 0.28, y: 0.35 },
      { x: 0.49, y: 0.23 },
      { x: 0.66, y: 0.24 },
      { x: 0.8, y: 0.37 },
      { x: 0.76, y: 0.56 },
      { x: 0.6, y: 0.7 },
      { x: 0.41, y: 0.74 },
      { x: 0.24, y: 0.69 },
    ],
  },
]

const getNextZoneId = (zones) => {
  const max = zones.reduce((acc, zone) => {
    const m = zone.id.match(/DPZ-(\d+)/)
    return Math.max(acc, m ? Number(m[1]) : 0)
  }, 0)
  return `DPZ-${String(max + 1).padStart(2, '0')}`
}

export default function ZoneConfig() {
  const [zones, setZones] = useState(() => createDefaultZones())
  const [activeZoneId, setActiveZoneId] = useState('DPZ-01')
  const [isEditMode, setIsEditMode] = useState(true)

  const [detectionSensitivity, setDetectionSensitivity] = useState(0.75)
  const [minimumChildHeight, setMinimumChildHeight] = useState(50)
  const [useAdultFilter, setUseAdultFilter] = useState(false)

  const [sendTelegramAlert, setSendTelegramAlert] = useState(true)
  const [activateSiren, setActivateSiren] = useState(false)
  const [logEvent, setLogEvent] = useState(false)

  const [streamError, setStreamError] = useState(false)
  const [streamKey, setStreamKey] = useState(0)
  const [dragIndex, setDragIndex] = useState(null)

  const overlayRef = useRef(null)

  const activeZone = useMemo(() => zones.find((z) => z.id === activeZoneId) || null, [zones, activeZoneId])
  const vertices = activeZone?.vertices || []

  const polygonPoints = useMemo(
    () => vertices.map((p) => `${p.x * 100},${p.y * 100}`).join(' '),
    [vertices],
  )

  const topVertex = useMemo(() => {
    if (vertices.length < 3) return null
    return vertices.reduce((top, p) => (p.y < top.y ? p : top), vertices[0])
  }, [vertices])

  const updateActiveVertices = (updater) => {
    if (!activeZone) return
    setZones((prev) =>
      prev.map((z) => {
        if (z.id !== activeZone.id) return z
        const next = typeof updater === 'function' ? updater(z.vertices) : updater
        return { ...z, vertices: next }
      }),
    )
  }

  const getPointer = (event) => {
    const svg = overlayRef.current
    if (!svg) return null
    const rect = svg.getBoundingClientRect()
    return {
      x: clamp01((event.clientX - rect.left) / rect.width),
      y: clamp01((event.clientY - rect.top) / rect.height),
    }
  }

  const handleOverlayClick = (event) => {
    if (!isEditMode || dragIndex !== null || !activeZone) return
    const p = getPointer(event)
    if (!p) return
    updateActiveVertices((prev) => [...prev, p])
  }

  const onVertexDown = (index) => (event) => {
    if (!isEditMode) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture?.(event.pointerId)
    setDragIndex(index)
  }

  const handlePointerMove = (event) => {
    if (!isEditMode || dragIndex === null) return
    const p = getPointer(event)
    if (!p) return
    updateActiveVertices((prev) => prev.map((v, i) => (i === dragIndex ? p : v)))
  }

  const stopDrag = () => setDragIndex(null)

  const handleAddVertex = () => {
    updateActiveVertices((prev) => {
      if (prev.length === 0) return [{ x: 0.5, y: 0.5 }]
      if (prev.length === 1) return [...prev, { x: clamp01(prev[0].x + 0.08), y: clamp01(prev[0].y + 0.08) }]
      const last = prev[prev.length - 1]
      const first = prev[0]
      return [...prev, { x: (last.x + first.x) / 2, y: (last.y + first.y) / 2 }]
    })
  }

  const handleRemoveVertex = () => updateActiveVertices((prev) => prev.slice(0, -1))
  const handleClearAll = () => updateActiveVertices([])

  const handleAddNewZone = () => {
    const id = getNextZoneId(zones)
    setZones((prev) => [...prev, { id, name: `Pool Zone ${zones.length + 1}`, vertices: [] }])
    setActiveZoneId(id)
    setIsEditMode(true)
  }

  const handleDeleteZone = (zoneId) => {
    const next = zones.filter((z) => z.id !== zoneId)
    if (next.length === 0) {
      const fallback = { id: 'DPZ-01', name: 'Pool Perimeter', vertices: [] }
      setZones([fallback])
      setActiveZoneId(fallback.id)
      return
    }
    setZones(next)
    if (activeZoneId === zoneId) setActiveZoneId(next[0].id)
  }

  const handleCancel = () => {
    const defaults = createDefaultZones()
    setZones(defaults)
    setActiveZoneId(defaults[0].id)
    setIsEditMode(true)
    setDetectionSensitivity(0.75)
    setMinimumChildHeight(50)
    setUseAdultFilter(false)
    setSendTelegramAlert(true)
    setActivateSiren(false)
    setLogEvent(false)
  }

  return (
    <section className="grid gap-4 xl:grid-cols-12">
      <div className="xl:col-span-9">
        <div className="rounded-xl border border-white/10 bg-[#1B2639] p-4 sm:p-5">
          <h2 className="text-xl font-semibold text-slate-100">DANGEROUS ZONE CONFIGURATION (ROI)</h2>
          <div className="mt-3 h-px bg-white/10" />

          <div className="relative mt-4 aspect-video overflow-hidden rounded-md border border-white/20 bg-[#0A111B]">
            {!streamError && (
              <>
                <img
                  key={streamKey}
                  src={LIVE_STREAM_URL}
                  alt="Live IP Camera"
                  className="absolute inset-0 h-full w-full object-fill"
                  draggable={false}
                  onError={() => setStreamError(true)}
                  onLoad={() => setStreamError(false)}
                />

                <svg
                  ref={overlayRef}
                  viewBox="0 0 100 100"
                  preserveAspectRatio="none"
                  className={`absolute inset-0 z-10 h-full w-full touch-none ${
                    isEditMode ? 'cursor-crosshair' : 'cursor-default'
                  }`}
                  onClick={handleOverlayClick}
                  onPointerMove={handlePointerMove}
                  onPointerUp={stopDrag}
                  onPointerCancel={stopDrag}
                  onPointerLeave={stopDrag}
                >
                  {vertices.length > 1 && vertices.length < 3 && (
                    <polyline points={polygonPoints} fill="none" stroke="rgba(251,146,60,0.95)" strokeWidth="1.1" />
                  )}

                  {vertices.length >= 3 && (
                    <polygon
                      points={polygonPoints}
                      fill="rgba(239,68,68,0.35)"
                      stroke="#fb923c"
                      strokeWidth="1.45"
                      strokeLinejoin="round"
                    />
                  )}

                  {vertices.map((p, index) => (
                    <circle
                      key={`${activeZone?.id || 'zone'}-${index}`}
                      cx={p.x * 100}
                      cy={p.y * 100}
                      r="1.05"
                      fill="#fff"
                      stroke="#fb923c"
                      strokeWidth="0.45"
                      className={isEditMode ? 'cursor-grab active:cursor-grabbing' : 'cursor-default'}
                      onPointerDown={onVertexDown(index)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  ))}
                </svg>
              </>
            )}

            {streamError && (
              <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-black/75">
                <TriangleAlert className="text-red-400" size={22} />
                <p className="text-sm font-semibold text-slate-100">Camera stream unavailable</p>
                <button
                  type="button"
                  onClick={() => {
                    setStreamError(false)
                    setStreamKey((v) => v + 1)
                  }}
                  className="rounded-md border border-white/20 bg-white/10 px-4 py-2 text-xs font-semibold text-slate-100"
                >
                  Retry
                </button>
              </div>
            )}

            <div className="absolute left-3 top-3 z-20 rounded bg-black/55 px-2.5 py-1 text-sm font-medium text-slate-100">
              IP Camera (Live Bantent)
            </div>

            {topVertex && activeZone && (
              <div
                className="absolute z-20 -translate-x-1/2 rounded border border-white/20 bg-black/65 px-2 py-1 text-[11px] font-semibold text-white"
                style={{ left: `${topVertex.x * 100}%`, top: `${Math.max(topVertex.y * 100 - 7, 2)}%` }}
              >
                Zone: {activeZone.name} (ID: {activeZone.id})
              </div>
            )}
          </div>

          <div className="mt-5 flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => setIsEditMode((v) => !v)}
              className="inline-flex h-11 min-w-[180px] items-center justify-center gap-2 rounded-lg bg-emerald-500 px-6 text-sm font-semibold text-white hover:bg-emerald-400"
            >
              <Pencil size={15} />
              EDIT ZONE
            </button>

            <button
              type="button"
              onClick={handleAddNewZone}
              className="inline-flex h-11 min-w-[180px] items-center justify-center gap-2 rounded-lg bg-sky-500 px-6 text-sm font-semibold text-white hover:bg-sky-400"
            >
              <Plus size={16} />
              ADD NEW ZONE
            </button>
          </div>
        </div>
      </div>

      <aside className="xl:col-span-3">
        <div className="flex h-full flex-col rounded-xl border border-white/10 bg-[#1B2639] p-4">
          <h3 className="text-lg font-semibold text-slate-100">CONFIGURATION TOOLS</h3>

          <div className="mt-4 space-y-5">
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">ZONE DRAWING TOOLS</h4>
              <div className="mt-2 grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={handleAddVertex}
                  className="inline-flex h-10 flex-col items-center justify-center rounded-md bg-emerald-500 text-[10px] font-semibold text-white hover:bg-emerald-400"
                >
                  <Plus size={14} />
                  ADD VERTEX
                </button>

                <button
                  type="button"
                  onClick={handleRemoveVertex}
                  className="inline-flex h-10 flex-col items-center justify-center rounded-md border border-white/20 bg-white/5 text-[10px] font-semibold text-slate-100 hover:bg-white/10"
                >
                  <Minus size={14} />
                  REMOVE VERTEX
                </button>

                <button
                  type="button"
                  onClick={handleClearAll}
                  className="inline-flex h-10 flex-col items-center justify-center rounded-md border border-white/20 bg-white/5 text-[10px] font-semibold text-slate-100 hover:bg-white/10"
                >
                  <Trash2 size={14} />
                  CLEAR ALL
                </button>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">AI ACCURACY</h4>
              <div className="mt-2 rounded-md border border-white/10 bg-white/[0.03] p-3">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-300">DETECTION SENSITIVITY</p>

                <svg viewBox="0 0 120 70" className="mt-2 h-20 w-full">
                  <path
                    d="M 10 60 A 50 50 0 0 1 110 60"
                    fill="none"
                    stroke="rgba(255,255,255,0.15)"
                    strokeWidth="10"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 10 60 A 50 50 0 0 1 110 60"
                    fill="none"
                    stroke="#22c55e"
                    strokeWidth="10"
                    strokeDasharray={`${Math.max(1, detectionSensitivity * GAUGE_ARC)} ${GAUGE_ARC}`}
                    strokeLinecap="round"
                  />
                  <text x="60" y="44" textAnchor="middle" fill="#e2e8f0" fontSize="14" fontWeight="700">
                    {detectionSensitivity.toFixed(2)}
                  </text>
                </svg>

                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={detectionSensitivity}
                  onChange={(e) => setDetectionSensitivity(Number(e.target.value))}
                  className="w-full accent-sky-500"
                />

                <div className="mt-1 flex justify-between text-[10px] font-semibold text-slate-400">
                  <span>LOW (0.0)</span>
                  <span>HIGH (1.0)</span>
                </div>

                <label className="mt-3 block text-[11px] font-semibold uppercase tracking-wider text-slate-300">
                  MINIMUM CHILD HEIGHT (Pixels)
                </label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={minimumChildHeight}
                  onChange={(e) => setMinimumChildHeight(Number(e.target.value) || 0)}
                  className="mt-1 h-9 w-full rounded-md border border-white/15 bg-[#0F1729] px-3 text-sm text-slate-100 outline-none focus:border-sky-400"
                />

                <label className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-slate-200">
                  <input
                    type="checkbox"
                    checked={useAdultFilter}
                    onChange={(e) => setUseAdultFilter(e.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-[#0F1729]"
                  />
                  USE ADULT-HEIGHT FILTER
                </label>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">ALERTING & LOGGING</h4>
              <div className="mt-2 space-y-2 rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs">
                <label className="inline-flex items-center gap-2 text-slate-200">
                  <input
                    type="checkbox"
                    checked={sendTelegramAlert}
                    onChange={(e) => setSendTelegramAlert(e.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-[#0F1729]"
                  />
                  SEND TELEGRAM ALERT
                </label>

                <label className="inline-flex items-center gap-2 text-slate-200">
                  <input
                    type="checkbox"
                    checked={activateSiren}
                    onChange={(e) => setActivateSiren(e.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-[#0F1729]"
                  />
                  ACTIVATE SIREN
                </label>

                <label className="inline-flex items-center gap-2 text-slate-200">
                  <input
                    type="checkbox"
                    checked={logEvent}
                    onChange={(e) => setLogEvent(e.target.checked)}
                    className="h-4 w-4 rounded border-white/20 bg-[#0F1729]"
                  />
                  LOG EVENT
                </label>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">ZONE LIST</h4>
              <ul className="mt-2 space-y-2">
                {zones.map((zone, index) => {
                  const selected = zone.id === activeZoneId
                  return (
                    <li
                      key={zone.id}
                      className={`flex items-center gap-2 rounded-md border px-2 py-2 text-sm ${
                        selected ? 'border-sky-400/70 bg-sky-500/10' : 'border-white/10 bg-white/[0.03]'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          setActiveZoneId(zone.id)
                          setIsEditMode(true)
                        }}
                        className="flex-1 text-left text-slate-100"
                      >
                        {index + 1}. {zone.name} <span className="text-emerald-300">(Active)</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          setActiveZoneId(zone.id)
                          setIsEditMode(true)
                        }}
                        className="rounded p-1 text-sky-400 hover:bg-sky-500/20"
                        aria-label={`Edit ${zone.name}`}
                      >
                        <Pencil size={14} />
                      </button>

                      <button
                        type="button"
                        onClick={() => handleDeleteZone(zone.id)}
                        className="rounded p-1 text-red-400 hover:bg-red-500/20"
                        aria-label={`Delete ${zone.name}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          </div>

          <div className="mt-auto border-t border-white/10 pt-4">
            <div className="flex gap-2">
              <button
                type="button"
                className="inline-flex h-10 flex-1 items-center justify-center rounded-md bg-emerald-500 px-3 text-xs font-semibold uppercase tracking-wider text-white hover:bg-emerald-400"
              >
                SAVE CONFIGURATION
              </button>

              <button
                type="button"
                onClick={handleCancel}
                className="inline-flex h-10 flex-1 items-center justify-center rounded-md border border-white/20 bg-white/5 px-3 text-xs font-semibold uppercase tracking-wider text-slate-100 hover:bg-white/10"
              >
                CANCEL
              </button>
            </div>
          </div>
        </div>
      </aside>
    </section>
  )
}