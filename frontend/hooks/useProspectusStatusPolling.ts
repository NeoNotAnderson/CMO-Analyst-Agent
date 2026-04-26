import { useEffect, useRef } from 'react';
import { Prospectus } from '@/types';

interface UseProspectusStatusPollingProps {
  prospectuses: Prospectus[];
  onStatusUpdate: () => Promise<void>;
  enabled?: boolean;
}

const PROCESSING_STATUSES = ['pending', 'parsing_index', 'parsing_sections', 'creating_chunks'];
const POLL_INTERVAL_MS = 8000; // 8 seconds — parsing is slow, no need to hammer the server

export function useProspectusStatusPolling({
  prospectuses,
  onStatusUpdate,
  enabled = true,
}: UseProspectusStatusPollingProps) {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  // Keep a stable ref to the latest callback so we don't restart the interval when it changes
  const onStatusUpdateRef = useRef(onStatusUpdate);
  onStatusUpdateRef.current = onStatusUpdate;

  const hasProcessing = enabled && prospectuses.some((p) =>
    PROCESSING_STATUSES.includes(p.parse_status)
  );

  useEffect(() => {
    if (!hasProcessing) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Only start a new interval if one isn't already running
    if (intervalRef.current) return;

    intervalRef.current = setInterval(async () => {
      await onStatusUpdateRef.current();
    }, POLL_INTERVAL_MS);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [hasProcessing]);
}
