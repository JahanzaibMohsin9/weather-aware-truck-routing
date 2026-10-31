import { useEffect, useState } from 'react'
import { Autocomplete, CircularProgress, TextField } from '@mui/material'
import PlaceIcon from '@mui/icons-material/PlaceOutlined'
import { api } from '../api/client'

const MIN_CHARS = 3
const DEBOUNCE_MS = 250
// Suggestions already fetched this session, by lower-cased query.
const cache = new Map<string, string[]>()

interface Props {
  label: string
  value: string
  onChange: (value: string) => void
  error?: string
}

/** A place text field with suggestions as you type. Free text still works. */
export default function PlaceField({ label, value, onChange, error }: Props) {
  const query = value.trim()
  const key = query.toLowerCase()
  const [fetched, setFetched] = useState<{ key: string; labels: string[] }>({ key: '', labels: [] })
  const [loadingKey, setLoadingKey] = useState<string | null>(null)

  useEffect(() => {
    if (query.length < MIN_CHARS || cache.has(key)) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoadingKey(key)
      api
        .places(query, controller.signal)
        .then(({ places }) => {
          const labels = places.map((p) => p.label)
          cache.set(key, labels)
          setFetched({ key, labels })
        })
        .catch(() => {}) // suggestions are optional; typing still works
        .finally(() => setLoadingKey((k) => (k === key ? null : k)))
    }, DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query, key])

  const options = query.length < MIN_CHARS ? [] : (cache.get(key) ?? (fetched.key === key ? fetched.labels : []))
  const loading = loadingKey === key

  return (
    <Autocomplete
      freeSolo
      options={options}
      filterOptions={(o) => o} // the server already matched them
      inputValue={value}
      onInputChange={(_, next) => onChange(next)}
      loading={loading}
      renderOption={({ key: optionKey, ...props }, option) => (
        <li key={optionKey} {...props}>
          <PlaceIcon fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
          {option}
        </li>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          placeholder="City, ST or address"
          required
          size="small"
          error={!!error}
          helperText={error}
          slotProps={{
            ...params.slotProps,
            input: {
              ...params.slotProps?.input,
              endAdornment: (
                <>
                  {loading && <CircularProgress size={16} sx={{ mr: 1 }} />}
                  {(params.slotProps?.input as { endAdornment?: React.ReactNode })?.endAdornment}
                </>
              ),
            },
          }}
        />
      )}
    />
  )
}
