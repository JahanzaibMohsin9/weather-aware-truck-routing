export function formatMiles(miles: number): string {
  if (miles === 0) return '0'
  return miles >= 10 ? Math.round(miles).toLocaleString() : miles.toFixed(1)
}

export function formatDuration(minutes: number): string {
  const total = Math.round(minutes)
  const h = Math.floor(total / 60)
  const m = total % 60
  return h === 0 ? `${m} min` : `${h} h ${m.toString().padStart(2, '0')} min`
}

const timeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

/** Local time in the viewer's time zone, e.g. "Sat 2:47 PM CDT". */
export function formatLocalTime(iso: string | Date): string {
  return timeFormat.format(typeof iso === 'string' ? new Date(iso) : iso)
}

/** Value for <input type="datetime-local"> in the viewer's time zone. */
export function toDateTimeLocal(date: Date): string {
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

/** The next quarter hour from now, as a sensible default departure. */
export function nextQuarterHour(now = new Date()): Date {
  const d = new Date(now)
  d.setSeconds(0, 0)
  d.setMinutes(Math.ceil((d.getMinutes() + 1) / 15) * 15)
  return d
}
