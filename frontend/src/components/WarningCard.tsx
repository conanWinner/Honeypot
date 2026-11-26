import type { RefObject } from 'react'
import type { Script } from '../lib/api'

export function WarningCard({ script, cardRef }: { script: Script; cardRef: RefObject<HTMLDivElement | null> }) {
  return (
    <div
      ref={cardRef}
      style={{
        width: 640,
        maxWidth: '100%',
        background: '#1c1915',
        color: '#f6efe4',
        padding: 28,
        borderRadius: 28,
        fontFamily: '"Be Vietnam Pro", sans-serif',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ letterSpacing: '0.16em', fontSize: 12, textTransform: 'uppercase', color: '#e7b089' }}>
          Honeypot · Cảnh báo lừa đảo
        </span>
        <span style={{ border: '1px solid #b64022', color: '#f0b2a2', borderRadius: 999, padding: '4px 10px', fontSize: 12 }}>
          {script.category_label}
        </span>
      </div>
      <h3 style={{ fontFamily: 'Fraunces, serif', fontSize: 32, lineHeight: 1.15, margin: '14px 0 8px' }}>{script.title}</h3>
      <p style={{ margin: 0, color: '#e6d7c4', lineHeight: 1.55 }}>{script.summary}</p>
      <ul style={{ margin: '16px 0', paddingLeft: 18, lineHeight: 1.5 }}>
        {script.red_flags.slice(0, 3).map((flag) => (
          <li key={flag}>{flag}</li>
        ))}
      </ul>
      <p style={{ margin: 0, background: '#f6efe4', color: '#1c1915', borderRadius: 16, padding: 14, lineHeight: 1.5 }}>
        {script.advice}
      </p>
    </div>
  )
}
