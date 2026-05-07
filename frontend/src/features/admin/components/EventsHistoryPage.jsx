import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Filter,
  RefreshCcw,
  Search,
  Siren,
} from 'lucide-react'
import { getAlertHistory, resolveAlertById } from '../api/events_history'

const FALLBACK_IMAGE = 'https://placehold.co/640x360/0f172a/e2e8f0?text=No+Snapshot'

const dateTimeFormatter = new Intl.DateTimeFormat('vi-VN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

function formatDateTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--'
  return dateTimeFormatter.format(date)
}

function normalizeConfidence(confidence) {
  if (typeof confidence !== 'number') return '--'
  return `${Math.round(confidence * 100)}%`
}

export default function EventsHistoryPage() {
  const [alerts, setAlerts] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [imageAttemptIndex, setImageAttemptIndex] = useState(0)
  const [searchText, setSearchText] = useState('')
  const [objectFilter, setObjectFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [isLoading, setIsLoading] = useState(false)
  const [isResolving, setIsResolving] = useState(false)
  const [error, setError] = useState('')

  const fetchAlerts = async () => {
    try {
      setIsLoading(true)
      setError('')

      const response = await getAlertHistory({
        q: searchText || undefined,
        object_type: objectFilter,
        resolved: statusFilter,
        limit: 200,
      })

      const history = response?.alerts || []
      setAlerts(history)

      if (!history.length) {
        setSelectedId(null)
        return
      }

      setSelectedId((previous) => {
        const exists = history.some((item) => item.id === previous)
        return exists ? previous : history[0].id
      })
    } catch (err) {
      setError('Không thể tải lịch sử cảnh báo. Kiểm tra backend Flask và kết nối DB.')
      console.error('Lỗi load alerts:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchAlerts()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const timer = setInterval(() => {
      fetchAlerts()
    }, 15000)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText, objectFilter, statusFilter])

  const selectedAlert = useMemo(
    () => alerts.find((item) => item.id === selectedId) || null,
    [alerts, selectedId],
  )

  const alertImageUrls = useMemo(() => {
    if (!selectedAlert) return []

    const urls = Array.isArray(selectedAlert.image_urls) ? selectedAlert.image_urls.filter(Boolean) : []
    if (urls.length > 0) return urls

    return selectedAlert.image_url ? [selectedAlert.image_url] : []
  }, [selectedAlert])

  const currentAlertImage = alertImageUrls[imageAttemptIndex] || FALLBACK_IMAGE

  useEffect(() => {
    setImageAttemptIndex(0)
  }, [selectedAlert?.id])

  const summary = useMemo(() => {
    const total = alerts.length
    const unresolved = alerts.filter((item) => !item.is_resolved).length
    const resolved = total - unresolved
    const child = alerts.filter((item) => String(item.object_type).toLowerCase() === 'child').length
    return { total, unresolved, resolved, child }
  }, [alerts])

  const handleApplyFilter = () => {
    fetchAlerts()
  }

  const handleResolveSelected = async () => {
    if (!selectedAlert || selectedAlert.is_resolved) return

    try {
      setIsResolving(true)
      await resolveAlertById(selectedAlert.id)
      setAlerts((current) =>
        current.map((item) => (item.id === selectedAlert.id ? { ...item, is_resolved: true } : item)),
      )
    } catch (err) {
      console.error('Lỗi resolve alert:', err)
      setError('Không thể cập nhật trạng thái cảnh báo.')
    } finally {
      setIsResolving(false)
    }
  }

  return (
    <section className="space-y-5">
      <div className="panel overflow-hidden p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="max-w-2xl">
            <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-sky-300">Event archive</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-50 md:text-3xl">DANGEROUS ZONE INTRUSION EVENTS HISTORY</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">Theo dõi mọi cảnh báo đã lưu từ hệ thống camera và AI detection.</p>
          </div>

          <button
            type="button"
            onClick={fetchAlerts}
            className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm font-semibold text-slate-200 transition hover:bg-white/10"
          >
            <RefreshCcw size={15} />
            Làm mới
          </button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-rose-400/20 bg-rose-500/10 p-4 shadow-[0_12px_30px_rgba(244,63,94,0.08)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-rose-200/80">Tổng sự kiện</p>
            <p className="mt-2 text-3xl font-semibold text-rose-100">{summary.total}</p>
          </div>

          <div className="rounded-2xl border border-amber-300/20 bg-amber-400/10 p-4 shadow-[0_12px_30px_rgba(245,158,11,0.08)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-100/80">Chưa xử lý</p>
            <p className="mt-2 text-3xl font-semibold text-amber-200">{summary.unresolved}</p>
          </div>

          <div className="rounded-2xl border border-emerald-300/20 bg-emerald-400/10 p-4 shadow-[0_12px_30px_rgba(16,185,129,0.08)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-emerald-100/80">Đã xử lý</p>
            <p className="mt-2 text-3xl font-semibold text-emerald-200">{summary.resolved}</p>
          </div>

          <div className="rounded-2xl border border-sky-300/20 bg-sky-400/10 p-4 shadow-[0_12px_30px_rgba(14,165,233,0.08)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-100/80">Phát hiện trẻ em</p>
            <p className="mt-2 text-3xl font-semibold text-sky-200">{summary.child}</p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="xl:col-span-8">
          <div className="panel overflow-hidden p-4 sm:p-5">
            <div className="flex flex-wrap items-center gap-2">
              <label className="relative min-w-[240px] flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
                <input
                  value={searchText}
                  onChange={(event) => setSearchText(event.target.value)}
                  placeholder="Tìm theo ID, zone, camera..."
                  className="h-11 w-full rounded-2xl border border-white/10 bg-white/5 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-orange-400/60 focus:bg-white/10 focus:ring-4 focus:ring-orange-500/10"
                />
              </label>

              <select
                value={objectFilter}
                onChange={(event) => setObjectFilter(event.target.value)}
                className="h-11 min-w-[150px] rounded-2xl border border-white/10 bg-white/5 px-3 text-sm text-slate-100 outline-none transition focus:border-orange-400/60 focus:bg-white/10 focus:ring-4 focus:ring-orange-500/10"
              >
                <option value="all">Tất cả đối tượng</option>
                <option value="child">Child</option>
                <option value="adult">Adult</option>
              </select>

              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className="h-11 min-w-[150px] rounded-2xl border border-white/10 bg-white/5 px-3 text-sm text-slate-100 outline-none transition focus:border-orange-400/60 focus:bg-white/10 focus:ring-4 focus:ring-orange-500/10"
              >
                <option value="all">Mọi trạng thái</option>
                <option value="open">Chưa xử lý</option>
                <option value="resolved">Đã xử lý</option>
              </select>

              <button
                type="button"
                onClick={handleApplyFilter}
                className="inline-flex h-11 items-center gap-2 rounded-2xl bg-[linear-gradient(135deg,#ff8c2c_0%,#ff6f26_100%)] px-4 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(255,116,44,0.2)] transition hover:translate-y-[-1px]"
              >
                <Filter size={15} />
                Lọc
              </button>
            </div>

            {error && <p className="mt-3 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</p>}

            <div className="mt-4 overflow-hidden rounded-3xl border border-white/10">
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead className="bg-white/5">
                    <tr>
                      {['Event ID', 'Timestamp', 'Object', 'Zone', 'Confidence', 'Status'].map((label) => (
                        <th
                          key={label}
                          className="whitespace-nowrap border-b border-white/10 px-3 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400"
                        >
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>

                  <tbody>
                    {isLoading && (
                      <tr>
                        <td colSpan={6} className="px-3 py-6 text-center text-sm text-slate-400">
                          Đang tải lịch sử cảnh báo...
                        </td>
                      </tr>
                    )}

                    {!isLoading && alerts.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-3 py-6 text-center text-sm text-slate-400">
                          Chưa có sự kiện cảnh báo nào được lưu.
                        </td>
                      </tr>
                    )}

                    {!isLoading &&
                      alerts.map((alert) => {
                        const isActive = alert.id === selectedId
                        return (
                          <tr
                            key={alert.id}
                            onClick={() => setSelectedId(alert.id)}
                            className={`cursor-pointer border-b border-white/5 transition-colors hover:bg-white/5 ${
                              isActive ? 'bg-orange-500/10' : ''
                            }`}
                          >
                            <td className="px-3 py-3 text-sm font-semibold text-slate-100">EVN-{String(alert.id).padStart(3, '0')}</td>
                            <td className="px-3 py-3 text-sm text-slate-300">{formatDateTime(alert.created_at)}</td>
                            <td className="px-3 py-3 text-sm text-slate-200">{alert.object_type || '--'}</td>
                            <td className="px-3 py-3 text-sm text-slate-200">{alert.zone_name || alert.zone_id || '--'}</td>
                            <td className="px-3 py-3 text-sm text-slate-200">{normalizeConfidence(alert.confidence)}</td>
                            <td className="px-3 py-3">
                              <span
                                className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-semibold ${
                                  alert.is_resolved
                                    ? 'border-emerald-300/30 bg-emerald-400/10 text-emerald-300'
                                    : 'border-amber-300/30 bg-amber-400/10 text-amber-300'
                                }`}
                              >
                                {alert.is_resolved ? 'Resolved' : 'Open'}
                              </span>
                            </td>
                          </tr>
                        )
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <aside className="xl:col-span-4">
          <div className="panel p-4">
            <h3 className="text-lg font-semibold text-slate-50">Event Detail Panel</h3>

            {!selectedAlert && (
              <p className="mt-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-400">
                Chọn một sự kiện để xem chi tiết.
              </p>
            )}

            {selectedAlert && (
              <div className="mt-3 space-y-3 text-sm">
                <p className="inline-flex items-center gap-2 text-base font-semibold text-slate-50">
                  <Siren size={17} className="text-orange-300" />
                  EVN-{String(selectedAlert.id).padStart(3, '0')}
                </p>

                <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/40">
                  <img
                    src={currentAlertImage}
                    alt={`Alert ${selectedAlert.id}`}
                    className="h-auto w-full object-cover"
                    onError={(event) => {
                      if (imageAttemptIndex < alertImageUrls.length - 1) {
                        setImageAttemptIndex((value) => value + 1)
                        return
                      }

                      event.currentTarget.src = FALLBACK_IMAGE
                    }}
                  />
                </div>

                <div className="space-y-2 rounded-2xl border border-white/10 bg-white/5 p-4">
                  <p className="flex items-center justify-between text-slate-300">
                    <span className="inline-flex items-center gap-2 text-slate-400">
                      <Clock3 size={14} />
                      Timestamp
                    </span>
                    <span>{formatDateTime(selectedAlert.created_at)}</span>
                  </p>

                  <p className="flex items-center justify-between text-slate-300">
                    <span>Camera</span>
                    <span>{selectedAlert.camera_name || `Camera ${selectedAlert.camera_id || '--'}`}</span>
                  </p>

                  <p className="flex items-center justify-between text-slate-300">
                    <span>Zone</span>
                    <span>{selectedAlert.zone_name || selectedAlert.zone_id || '--'}</span>
                  </p>

                  <p className="flex items-center justify-between text-slate-300">
                    <span>Object</span>
                    <span>{selectedAlert.object_type || '--'}</span>
                  </p>

                  <p className="flex items-center justify-between text-slate-300">
                    <span>Confidence</span>
                    <span>{normalizeConfidence(selectedAlert.confidence)}</span>
                  </p>

                  <p className="flex items-center justify-between text-slate-300">
                    <span>Status</span>
                    <span className={selectedAlert.is_resolved ? 'text-emerald-300' : 'text-amber-300'}>
                      {selectedAlert.is_resolved ? 'Resolved' : 'Open'}
                    </span>
                  </p>
                </div>

                <div className="grid gap-2 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={handleResolveSelected}
                    disabled={selectedAlert.is_resolved || isResolving}
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl bg-emerald-500 px-3 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(16,185,129,0.2)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <CheckCircle2 size={16} />
                    {selectedAlert.is_resolved ? 'Đã xử lý' : isResolving ? 'Đang cập nhật...' : 'Xác nhận xử lý'}
                  </button>

                  <button
                    type="button"
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-3 text-sm font-semibold text-rose-200"
                  >
                    <AlertTriangle size={16} />
                    Cảnh báo mức cao
                  </button>
                </div>
              </div>
            )}
          </div>
        </aside>
      </div>
    </section>
  )
}
