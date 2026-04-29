import { useEffect, useState } from 'react'
import { Maximize2, Play, RefreshCw, X } from 'lucide-react'
import { ADMIN_CAMERA_GRID_URL, cameraVideoFeedUrl } from '../../../config/serviceUrls'

function CameraSkeleton() {
  return (
    <div className="overflow-hidden rounded-3xl border border-white/10 bg-[#111827] shadow-[0_18px_50px_rgba(0,0,0,0.22)]">
      <div className="aspect-video animate-pulse bg-gradient-to-br from-slate-800 via-slate-700 to-slate-800" />
      <div className="space-y-4 p-4">
        <div className="h-5 w-2/3 animate-pulse rounded bg-slate-700" />
        <div className="h-4 w-1/2 animate-pulse rounded bg-slate-700" />
        <div className="h-4 w-1/3 animate-pulse rounded bg-slate-700" />
      </div>
    </div>
  )
}

export default function AdminCameraGrid() {
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedCamera, setSelectedCamera] = useState(null)

  const loadCameras = async () => {
    setLoading(true)
    setError('')

    try {
      const authToken = localStorage.getItem('authToken') || sessionStorage.getItem('authToken')
      const response = await fetch(ADMIN_CAMERA_GRID_URL, {
        credentials: 'include',
        headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
      })

      const payload = await response.json()

      if (!response.ok) {
        throw new Error(payload?.message || 'Failed to load camera grid')
      }

      setCameras(Array.isArray(payload?.data) ? payload.data : [])
    } catch (fetchError) {
      setError(fetchError?.message || 'Không tải được danh sách camera')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCameras()
  }, [])

  useEffect(() => {
    if (!selectedCamera) return

    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        setSelectedCamera(null)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedCamera])

  return (
    <section className="min-h-screen bg-[#0B1220] px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-col gap-4 rounded-3xl border border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.16),_transparent_32%),linear-gradient(135deg,#101827_0%,#0B1220_100%)] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)] sm:p-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-300">Admin Dashboard</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Camera Grid View</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-300">
              Theo dõi toàn bộ camera theo dạng lưới, xem chủ sở hữu, trạng thái và mở stream trực tiếp khi cần.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={loadCameras}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:bg-white/10"
            >
              <RefreshCw size={16} />
              Refresh
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-5 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {error}
          </div>
        )}

        {loading ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <CameraSkeleton key={index} />
            ))}
          </div>
        ) : cameras.length === 0 ? (
          <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-slate-300">
            Không có camera nào trong hệ thống.
          </div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {cameras.map((camera) => {
              const isOnline = Boolean(Number(camera.is_online))
              const feedUrl = cameraVideoFeedUrl(camera.camera_id)

              return (
                <button
                  key={camera.camera_id}
                  type="button"
                  onClick={() => setSelectedCamera(camera)}
                  className="group overflow-hidden rounded-3xl border border-white/10 bg-[#111827] text-left shadow-[0_18px_50px_rgba(0,0,0,0.22)] transition duration-200 hover:-translate-y-1 hover:border-sky-400/30 hover:shadow-[0_24px_65px_rgba(14,165,233,0.14)]"
                >
                  <div className="relative aspect-video overflow-hidden bg-black">
                    <img
                      src={feedUrl}
                      alt={camera.camera_name}
                      className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
                      crossOrigin="use-credentials"
                      loading="lazy"
                    />

                    <div className="absolute left-3 top-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/55 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-100 backdrop-blur-sm">
                      <Play size={12} className="text-emerald-300" />
                      Live
                    </div>

                    <div
                      className={`absolute right-3 top-3 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] ${
                        isOnline ? 'bg-emerald-400/15 text-emerald-300' : 'bg-slate-500/15 text-slate-300'
                      }`}
                    >
                      {isOnline ? 'Online' : 'Offline'}
                    </div>

                    <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent opacity-90" />
                    <div className="absolute bottom-3 right-3 rounded-full border border-white/10 bg-black/50 p-2 text-white/90 backdrop-blur-sm">
                      <Maximize2 size={16} />
                    </div>
                  </div>

                  <div className="space-y-3 p-4">
                    <div>
                      <h3 className="line-clamp-1 text-lg font-semibold text-slate-50">{camera.camera_name}</h3>
                      <p className="mt-1 line-clamp-2 text-sm text-slate-400">{camera.location_note || 'Không có ghi chú vị trí'}</p>
                    </div>

                    <div className="flex items-center justify-between gap-3 text-sm text-slate-300">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Owner</p>
                        <p className="mt-1 font-medium text-slate-100">{camera.owner_name || 'Unknown Owner'}</p>
                        <p className="mt-1 text-xs text-slate-500">{camera.owner_username ? `@${camera.owner_username}` : 'No owner account'}</p>
                      </div>

                      <div className="text-right">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Status</p>
                        <p className={`mt-1 font-semibold ${isOnline ? 'text-emerald-300' : 'text-slate-300'}`}>
                          {camera.status || (isOnline ? 'online' : 'offline')}
                        </p>
                      </div>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {selectedCamera && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 px-4 py-6 backdrop-blur-sm"
          onClick={() => setSelectedCamera(null)}
        >
          <div
            className="relative w-full max-w-6xl overflow-hidden rounded-[28px] border border-white/10 bg-[#0F172A] shadow-[0_30px_100px_rgba(0,0,0,0.45)]"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setSelectedCamera(null)}
              className="absolute right-4 top-4 z-20 rounded-full border border-white/10 bg-black/50 p-2 text-white/90 transition hover:bg-black/70"
            >
              <X size={18} />
            </button>

            <div className="grid gap-0 lg:grid-cols-[1.4fr_0.6fr]">
              <div className="bg-black">
                <img
                  src={cameraVideoFeedUrl(selectedCamera.camera_id)}
                  alt={selectedCamera.camera_name}
                  className="h-full min-h-[320px] w-full object-cover lg:min-h-[70vh]"
                  crossOrigin="use-credentials"
                />
              </div>

              <div className="space-y-6 p-6 lg:p-8">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-300">Camera detail</p>
                  <h2 className="mt-2 text-2xl font-semibold text-slate-50">{selectedCamera.camera_name}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{selectedCamera.location_note || 'Không có ghi chú vị trí'}</p>
                </div>

                <div className="grid gap-3 text-sm text-slate-300">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Owner</p>
                    <p className="mt-1 font-medium text-slate-100">{selectedCamera.owner_name || 'Unknown Owner'}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {selectedCamera.owner_username ? `@${selectedCamera.owner_username}` : 'No owner account'}
                    </p>
                    {selectedCamera.owner_email && <p className="mt-1 text-xs text-slate-500">{selectedCamera.owner_email}</p>}
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Status</p>
                    <p className="mt-1 font-semibold text-slate-100">{selectedCamera.status || 'unknown'}</p>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Active</p>
                    <p className="mt-1 font-semibold text-slate-100">
                      {selectedCamera.is_active ? 'active' : 'inactive'}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Camera ID</p>
                    <p className="mt-1 font-semibold text-slate-100">{selectedCamera.camera_id}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
