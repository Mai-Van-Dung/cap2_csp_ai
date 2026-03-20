import {
  Activity,
  Bell,
  BellRing,
  Camera,
  ChevronRight,
  Maximize2,
  Play,
  Send,
  Settings,
  SlidersHorizontal,
  TriangleAlert,
  Users,
  Volume2,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

// Connect this to your Python/OpenCV MJPEG stream endpoint (e.g., /video_feed)
const LIVE_STREAM_URL =
  import.meta.env.VITE_LIVE_STREAM_URL || 'https://placehold.co/1280x720/0A111B/E2E8F0?text=Live+Stream'

const latestNotifications = [
  {
    id: 'PUSH-001',
    message: 'Child intrusion detected in Pool ROI.',
    time: '2024-05-22 14:35:10',
    tone: 'danger',
  },
  {
    id: 'PUSH-002',
    message: 'Telegram alert sent to guardians.',
    time: '2024-05-22 14:35:12',
    tone: 'info',
  },
  {
    id: 'PUSH-003',
    message: 'Manual siren remains in standby mode.',
    time: '2024-05-22 14:35:15',
    tone: 'info',
  },
]

function toneClass(tone) {
  if (tone === 'danger') return 'border-danger/60 bg-danger/10'
  return 'border-white/10 bg-white/[0.03]'
}

export default function LiveMonitor() {
  const [supervisedMode, setSupervisedMode] = useState(true)
  const [streamError, setStreamError] = useState(false)
  const [streamKey, setStreamKey] = useState(0)
  const streamContainerRef = useRef(null)
  const overlayCanvasRef = useRef(null)

  const handleRetryStream = () => {
    setStreamError(false)
    setStreamKey((value) => value + 1)
  }

  useEffect(() => {
    if (streamError) return

    const container = streamContainerRef.current
    const canvas = overlayCanvasRef.current
    if (!container || !canvas) return

    const syncCanvasSize = () => {
      canvas.width = container.clientWidth
      canvas.height = container.clientHeight
    }

    syncCanvasSize()

    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(syncCanvasSize)
    observer.observe(container)

    return () => observer.disconnect()
  }, [streamError, streamKey])

  return (
    <section className="grid gap-5 xl:grid-cols-12">
      <div className="xl:col-span-9">
        <div className="panel border-white/10 bg-[#1E2738] p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-semibold text-slate-100">LIVE POOL MONITOR & INTRUSION DETECTION</h2>

            <div
              className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wider ${
                supervisedMode
                  ? 'border-danger/70 bg-danger/10 text-danger'
                  : 'border-white/20 bg-white/5 text-slate-300'
              }`}
            >
              <TriangleAlert size={13} />
              <span>Supervised Swimming Mode</span>
              <button
                type="button"
                role="switch"
                aria-checked={supervisedMode}
                onClick={() => setSupervisedMode((value) => !value)}
                className={`relative h-5 w-10 rounded-full border transition ${
                  supervisedMode ? 'border-danger/60 bg-danger' : 'border-white/20 bg-slate-600'
                }`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                    supervisedMode ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </button>
            </div>
          </div>

          <div className="mt-3 h-px bg-white/10" />

          <div
            ref={streamContainerRef}
            className="relative mt-3 aspect-video w-full overflow-hidden rounded-md border border-white/20 bg-[#0A111B]"
          >
            {!streamError && (
              <>
                <img
                  key={streamKey}
                  src={LIVE_STREAM_URL}
                  alt="Live pool camera stream"
                  className="h-full w-full object-cover"
                  onLoad={() => setStreamError(false)}
                  onError={() => setStreamError(true)}
                />
                <canvas ref={overlayCanvasRef} className="absolute inset-0 z-10 h-full w-full bg-transparent" />
              </>
            )}

            {streamError && (
              <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-3 bg-black/80 px-4 text-center">
                <TriangleAlert size={24} className="text-danger" />
                <p className="text-base font-semibold text-slate-100">Camera Offline</p>
                <button
                  type="button"
                  onClick={handleRetryStream}
                  className="rounded-md border border-white/20 bg-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-slate-100 hover:bg-white/20"
                >
                  Retry
                </button>
              </div>
            )}

            <div className="absolute left-3 top-3 z-20 rounded bg-black/50 px-2.5 py-1 text-sm font-medium text-slate-100">
              IP Camera (Live Bantent)
            </div>

            <div className="absolute right-3 top-3 z-20 rounded bg-black/45 px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-slate-200">
              RTSP STREAM
            </div>

            <div className="absolute bottom-16 right-4 z-20 w-[210px] rounded-lg border border-white/40 bg-black/45 px-3 py-2 text-xs text-slate-200 backdrop-blur-sm">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-slate-100">SYSTEM HEALTH</p>
                <X size={14} className="text-slate-300" />
              </div>
              <p className="mt-1">
                CAM: <span className={streamError ? 'text-danger' : 'text-emerald-300'}>{streamError ? 'OFFLINE' : 'ONLINE'}</span>
              </p>
              <p>
                AI ENGINE: <span className="text-emerald-300">RUNNING (24 FPS)</span>
              </p>
            </div>

            <div className="absolute inset-x-0 bottom-0 z-20 border-t border-white/20 bg-black/60 px-3 py-2 text-xs text-slate-200">
              <div className="flex items-center gap-2">
                <Play size={12} className="text-white" />
                <Volume2 size={14} />
                <div className="h-1.5 w-44 rounded-full bg-white/20">
                  <div className="h-1.5 w-1/3 rounded-full bg-danger" />
                </div>
                <span className="hidden sm:inline">2024-05-22 14:35:10</span>

                <div className="ml-auto flex items-center gap-3 text-slate-100">
                  <Settings size={14} />
                  <Maximize2 size={14} />
                </div>
              </div>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-center gap-4">
            <button
              type="button"
              className="inline-flex h-12 min-w-[220px] items-center justify-center gap-2 rounded-lg bg-sky-500 px-6 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(56,189,248,0.38)] hover:bg-sky-400"
            >
              <Camera size={18} />
              TAKE SNAPSHOT
            </button>

            <button
              type="button"
              className="inline-flex h-12 min-w-[220px] items-center justify-center gap-2 rounded-lg bg-danger px-6 text-sm font-semibold text-white shadow-[0_10px_24px_rgba(255,77,77,0.42)] hover:bg-danger/90"
            >
              <BellRing size={18} />
              MANUAL SIREN
            </button>
          </div>
        </div>
      </div>

      <aside className="space-y-5 xl:col-span-3">
        <div className="panel border-white/10 bg-[#1E2738] p-4">
          <h3 className="text-lg font-semibold text-slate-100">LIVE CONTROL PANEL</h3>

          <div className="mt-3 space-y-2">
            <Link
              to="/events-history"
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-primary text-sm font-semibold text-[#1A1A1A] hover:bg-[#ff9b25]"
            >
              GO TO EVENTS HISTORY
              <ChevronRight size={16} />
            </Link>

            <Link
              to="/ai-settings"
              className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 text-sm font-semibold text-slate-100 hover:bg-white/10"
            >
              <SlidersHorizontal size={16} />
              ADJUST AI SETTINGS
            </Link>
          </div>
        </div>

        <div className="panel border-white/10 bg-[#1E2738] p-5">
          <h3 className="text-lg font-semibold text-slate-100">LIVE CONTROL PANEL</h3>

          <div className="mt-4 space-y-4 text-sm">
            <div className="flex items-start gap-3">
              <span className="mt-1 h-3 w-3 rounded-full bg-emerald-400" />
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-300">CAMERA STATUS:</p>
                <p className="mt-0.5 font-semibold text-emerald-300">ONLINE</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Activity size={17} className="mt-0.5 shrink-0 text-emerald-300" />
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-300">CURRENT FPS:</p>
                <p className="mt-0.5 font-semibold text-slate-100">24 (NORMAL)</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Users size={17} className="mt-0.5 shrink-0 text-danger" />
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-300">DETECTION COUNT:</p>
                <p className="mt-0.5 font-semibold text-slate-100">1 CHILD (ALERT), 2 ADULTS</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Send size={17} className="mt-0.5 shrink-0 text-sky-400" />
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-300">NOTIFICATIONS:</p>
                <p className="mt-0.5 font-semibold text-slate-100">TELEGRAM [ACTIVE]</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <BellRing size={17} className="mt-0.5 shrink-0 text-danger" />
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-300">SIREN:</p>
                <p className="mt-0.5 font-semibold text-slate-100">[STANDBY]</p>
              </div>
            </div>
          </div>

          <div className="mt-5 border-t border-white/10 pt-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">Latest Push Notifications</h4>
            <ul className="mt-3 space-y-2">
              {latestNotifications.map((item) => (
                <li key={item.id} className={`rounded-md border px-3 py-2 ${toneClass(item.tone)}`}>
                  <p className="inline-flex items-start gap-2 text-sm text-slate-100">
                    <Bell
                      size={14}
                      className={`mt-0.5 shrink-0 ${item.tone === 'danger' ? 'text-danger' : 'text-primary'}`}
                    />
                    {item.message}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{item.time}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </aside>
    </section>
  )
}