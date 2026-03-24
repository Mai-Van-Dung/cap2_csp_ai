import { MoveRight } from 'lucide-react'

export default function PlaceholderPage({ title, description }) {
  return (
    <section className="panel p-6 md:p-8">
      <h2 className="text-2xl font-semibold text-slate-100">{title}</h2>
      <p className="mt-2 max-w-xl text-sm text-slate-400">{description}</p>

      <div className="mt-6 inline-flex items-center gap-2 rounded-md border border-primary/40 bg-primary/10 px-4 py-2 text-sm text-primary">
        Section ready for next implementation
        <MoveRight size={16} />
      </div>
    </section>
  )
}