import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Runs `loader` when `deps` change and tracks loading / error / data.
 * Stale responses are ignored, so fast filter changes cannot show old results.
 */
export function useAsync(loader, deps = []) {
  const [state, setState] = useState({ status: 'loading', data: null, error: null });
  const [version, setVersion] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    let cancelled = false;
    setState((previous) => ({ ...previous, status: 'loading', error: null }));
    loaderRef.current().then(
      (data) => {
        if (!cancelled) setState({ status: 'success', data, error: null });
      },
      (error) => {
        if (!cancelled) setState({ status: 'error', data: null, error });
      },
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, loading: state.status === 'loading', reload };
}

/** Delays updating a value until typing pauses, to avoid one request per keystroke. */
export function useDebouncedValue(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
