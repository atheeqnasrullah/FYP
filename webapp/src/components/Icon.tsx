const PATHS: Record<string, string> = {
  dashboard: 'M3 13h8V3H3zm10 8h8V11h-8zM3 21h8v-6H3zm10-18v6h8V3z',
  patients: 'M16 11a4 4 0 1 0-4-4 4 4 0 0 0 4 4zm-8 0a3 3 0 1 0-3-3 3 3 0 0 0 3 3zm0 2c-2.7 0-6 1.3-6 3.5V19h6v-2.5c0-1.1.5-2.1 1.4-2.9A9 9 0 0 0 8 13zm8 0c-3 0-7 1.5-7 4v2h14v-2c0-2.5-4-4-7-4z',
  sessions: 'M4 5h16v2H4zm0 6h16v2H4zm0 6h10v2H4z',
  games: 'M7 6h10a5 5 0 0 1 0 10h-1l-2 2h-4l-2-2H7A5 5 0 0 1 7 6zm0 3v2H5v2h2v2h2v-2h2v-2H9V9zm9 1a1 1 0 1 0 1 1 1 1 0 0 0-1-1zm2 2a1 1 0 1 0 1 1 1 1 0 0 0-1-1z',
  datasets: 'M12 3C7 3 4 4.6 4 6.5v11C4 19.4 7 21 12 21s8-1.6 8-3.5v-11C20 4.6 17 3 12 3zm0 2c3.9 0 6 1.1 6 1.5S15.9 8 12 8 6 6.9 6 6.5 8.1 5 12 5zM6 9.2C7.5 9.7 9.6 10 12 10s4.5-.3 6-.8V12c0 .4-2.1 1.5-6 1.5S6 12.4 6 12zm0 5.5c1.5.5 3.6.8 6 .8s4.5-.3 6-.8v2.8c0 .4-2.1 1.5-6 1.5s-6-1.1-6-1.5z',
  settings: 'M19.4 13a7.5 7.5 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.6 7.6 0 0 0-1.7-1L15 3h-4l-.4 2.9a7.6 7.6 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.5 7.5 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a7.6 7.6 0 0 0 1.7 1L11 21h4l.4-2.9a7.6 7.6 0 0 0 1.7-1l2.5 1 2-3.5zM13 15.5a3.5 3.5 0 1 1 3.5-3.5 3.5 3.5 0 0 1-3.5 3.5z',
  pulse: 'M3 12h4l3-8 4 16 3-8h4',
  hardware: 'M7 2h2v4h6V2h2v4h1a1 1 0 0 1 1 1v4a6 6 0 0 1-5 5.9V22h-4v-5.1A6 6 0 0 1 5 11V7a1 1 0 0 1 1-1h1z',
  clock: 'M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm1 10.4 3.5 2.1-1 1.7L11 13V7h2z',
  target: 'M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 4a6 6 0 1 1-6 6 6 6 0 0 1 6-6zm0 3a3 3 0 1 0 3 3 3 3 0 0 0-3-3z',
  menu: 'M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z',
  sun: 'M12 7a5 5 0 1 0 5 5 5 5 0 0 0-5-5zm0-5 1 3h-2zm0 20-1-3h2zM2 12l3-1v2zm20 0-3 1v-2zM4.9 4.9l2.8 1.4-1.4 1.4zm14.2 14.2-2.8-1.4 1.4-1.4zM4.9 19.1l1.4-2.8 1.4 1.4zM19.1 4.9l-1.4 2.8-1.4-1.4z',
  moon: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
}

export function Icon({ name, size = 18 }: { name: keyof typeof PATHS | string; size?: number }) {
  const d = PATHS[name]
  const stroke = name === 'pulse'
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill={stroke ? 'none' : 'currentColor'} stroke={stroke ? 'currentColor' : undefined} strokeWidth={stroke ? 2 : undefined} strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  )
}
