// Logo "Mesa Experta Regulatoria" — red de conocimiento (concepto A).
// variant 'light': cuadrado navy con nodos claros (para fondos claros: login).
// variant 'dark':  cuadrado blanco con nodos navy (para el sidebar navy).

export default function Logo({ size = 40, variant = 'light' }: { size?: number; variant?: 'light' | 'dark' }) {
  const dark = variant === 'dark'
  const bg = dark ? '#ffffff' : '#0f2547'
  const nodo = dark ? '#0f2547' : '#ffffff' // nodos "principales"
  const edge = dark ? '#a9bcd6' : '#5b7bc4'
  const azul = '#2563eb'
  const rojo = '#dc0014'
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" role="img" aria-label="Mesa Experta Regulatoria">
      <rect width="100" height="100" rx="24" fill={bg} />
      <g stroke={edge} strokeWidth="2.6" opacity="0.75">
        <line x1="32" y1="38" x2="58" y2="30" />
        <line x1="32" y1="38" x2="40" y2="72" />
        <line x1="58" y1="30" x2="74" y2="60" />
        <line x1="40" y1="72" x2="74" y2="60" />
        <line x1="58" y1="30" x2="40" y2="72" />
      </g>
      <circle cx="58" cy="30" r="8.5" fill={nodo} />
      <circle cx="32" cy="38" r="6.5" fill={azul} />
      <circle cx="40" cy="72" r="6.5" fill={nodo} />
      <circle cx="74" cy="60" r="7.5" fill={rojo} />
    </svg>
  )
}
