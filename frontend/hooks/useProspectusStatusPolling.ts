/**
 * Hook for polling prospectus status updates
 *
 * Polls the backend every 3 seconds when any prospectus is in a processing state
 * to detect when parsing completes and trigger UI updates.
 */

import { useEffect, useRef } from 'react';
import { Prospectus } from '@/types';

interface UseProspectusStatusPollingProps {
  prospectuses: Prospectus[];
  onStatusUpdate: () => Promise<void>;
  enabled?: boolean;
}

const PROCESSING_STATUSES = ['pending', 'parsing_index', 'parsing_sections'];
const POLL_INTERVAL_MS = 3000; // 3 seconds

export function useProspectusStatusPolling({
  prospectuses,
  onStatusUpdate,
  enabled = true,
}: UseProspectusStatusPollingProps) {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!enabled) {
      // Clear any existing interval if polling is disabled
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    // Check if any prospectus is in a processing state
    const hasProcessingProspectus = prospectuses.some((p) =>
      PROCESSING_STATUSES.includes(p.parse_status)
    );

    if (hasProcessingProspectus) {
      // Start polling
      console.log('[Polling] Starting status polling - processing prospectuses detected');

      intervalRef.current = setInterval(async () => {
        console.log('[Polling] Checking for status updates...');
        await onStatusUpdate();
      }, POLL_INTERVAL_MS);
    } else {
      // No processing prospectuses, clear interval
      if (intervalRef.current) {
        console.log('[Polling] Stopping status polling - no processing prospectuses');
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    // Cleanup on unmount or dependency change
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [prospectuses, onStatusUpdate, enabled]);

  return {
    isPolling: intervalRef.current !== null,
  };
}
