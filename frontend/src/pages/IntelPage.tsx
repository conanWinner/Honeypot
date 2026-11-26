import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { IocLinks } from '../components/Intel'
import { Banner, Button } from '../components/ui'
import { api, type IocLink } from '../lib/api'

type Node = { id: string; type: string; label: string; ref?: string; kind_label?: string }
type Cluster = { id: number; sources: Node[]; shared: Node[]; categories: string[]; cross_family: boolean }
type Graph = {
  clusters: Cluster[]
  stats: { sources: number; iocs: number; shared_iocs: number; linked_clusters: number; cross_family_clusters: number }
}

export function IntelPage() {
  const [graph, setGraph] = useState<Graph | null>(null)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<IocLink[] | null>(null)

  useEffect(() => {
    api<Graph>('/api/intel/graph')
      .then(setGraph)
      .catch((reason: Error) => setError(reason.message))
  }, [])

  async function search() {
    if (query.trim().length < 4) return
    const data = await api<{ hits: IocLink[] }>(`/api/intel/lookup?q=${encodeURIComponent(query.trim())}`)
    setHits(data.hits)
  }

  if (error) return <Banner tone="danger">{error}</Banner>
  if (!graph) return <p className="text-ink-soft">Đang dựng mạng lưới…</p>
  const linked = graph.clusters.filter((cluster) => cluster.shared.length > 0)

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.16em] text-seal">Mạng lưới chỉ dấu</p>
        <h1 className="mt-2 font-display text-4xl">Cùng một tài khoản, nhiều câu chuyện</h1>
      </div>
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {[
          ['Nguồn', graph.stats.sources],
          ['Chỉ dấu', graph.stats.iocs],
          ['Dùng chung', graph.stats.shared_iocs],
          ['Cụm liên kết', graph.stats.linked_clusters],
          ['Vượt loại lừa', graph.stats.cross_family_clusters],
        ].map(([label, value]) => (
          <div key={String(label)} className="dossier rounded-3xl p-4">
            <p className="font-display text-3xl text-seal">{value}</p>
            <p className="text-xs text-ink-soft">{label}</p>
          </div>
        ))}
      </section>
      <section className="dossier rounded-3xl p-5">
        <h2 className="font-display text-2xl">Tra một chỉ dấu</h2>
        <div className="mt-3 flex gap-2">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => event.key === 'Enter' && void search()}
            placeholder="Số tài khoản, tên miền, ví, t.me/…"
            className="h-10 flex-1 rounded-full border border-line bg-card px-4 text-sm"
          />
          <Button variant="seal" onClick={() => void search()}>
            Tra
          </Button>
        </div>
        {hits && <div className="mt-3">{hits.length ? <IocLinks links={hits} /> : <p className="text-sm text-ink-soft">Chưa thấy chỉ dấu này.</p>}</div>}
      </section>
      <section className="space-y-4">
        {linked.map((cluster) => (
          <article key={cluster.id} className="dossier rounded-3xl p-5">
            <p className="text-sm text-ink-soft">{cluster.categories.join(' · ') || 'Chưa phân loại'}</p>
            <p className="mt-1 text-sm">
              {cluster.shared.map((node) => (
                <b key={node.id} className="mr-2">
                  {node.kind_label} {node.label}
                </b>
              ))}
            </p>
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              {cluster.sources.map((src) => (
                <Link key={src.id} className="underline" to={src.type === 'script' ? `/canh-bao/kich-ban/${src.ref}` : `/phan-tich/hoi-thoai/${src.ref}`}>
                  {src.label}
                </Link>
              ))}
            </div>
          </article>
        ))}
      </section>
    </div>
  )
}
