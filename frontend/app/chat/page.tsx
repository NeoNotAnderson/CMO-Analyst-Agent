/**
 * Chat Page
 *
 * Main chat interface after login with session initialization
 */
'use client'

import {useState, useEffect, useCallback} from 'react';
import Header from '@/components/Header';
import ChatInterface from '@/components/ChatInterface';
import ProspectusSidebar from '@/components/ProspectusSidebar';
import UploadModal from '@/components/UploadModal';
import { getCurrentUser, initializeSession, getProspectusList, setActiveProspectus } from '@/lib/api';
import { useProspectusStatusPolling } from '@/hooks/useProspectusStatusPolling';
import type { Prospectus } from '@/types';

export default function ChatPage() {
  const [username, setUsername] = useState<string>('');
  const [prospectuses, setProspectuses] = useState<Prospectus[]>([]);
  const [activeProspectusId, setActiveProspectusId] = useState<string | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initialize = async () => {
      try {
        // Get current user
        const user = await getCurrentUser();
        setUsername(user.username);

        // Initialize session and get prospectuses
        const sessionData = await initializeSession();
        setProspectuses(sessionData.prospectuses);

        // Set first completed prospectus as active (if any)
        const completedProspectus = sessionData.prospectuses.find(
          p => p.parse_status === 'completed'
        );
        if (completedProspectus) {
          setActiveProspectusId(completedProspectus.prospectus_id);
          // Also notify backend
          await setActiveProspectus(completedProspectus.prospectus_id);
        }
      } catch (error) {
        console.error('Failed to initialize session', error);
      } finally {
        setIsLoading(false);
      }
    };
    initialize();
  }, []);

  const handleSelectProspectus = async (prospectusId: string) => {
    setActiveProspectusId(prospectusId);

    // Notify backend to update session
    try {
      await setActiveProspectus(prospectusId);
    } catch (error) {
      console.error('Failed to set active prospectus in backend:', error);
    }
  };

  const handleUploadComplete = async (prospectusId: string) => {
    // Refresh prospectuses list
    try {
      const updatedProspectuses = await getProspectusList();
      setProspectuses(updatedProspectuses);
      setActiveProspectusId(prospectusId);
    } catch (error) {
      console.error('Failed to refresh prospectuses', error);
    }
  };

  // Callback for status polling to refresh prospectus list
  const refreshProspectusList = useCallback(async () => {
    try {
      const updatedProspectuses = await getProspectusList();
      setProspectuses(updatedProspectuses);
    } catch (error) {
      console.error('Failed to refresh prospectuses during polling', error);
    }
  }, []);

  // Enable status polling to detect when parsing completes
  useProspectusStatusPolling({
    prospectuses,
    onStatusUpdate: refreshProspectusList,
    enabled: !isLoading,
  });

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading session...</p>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      <Header
        showLogout={true}
        username={username}
        onUploadClick={() => setIsUploadModalOpen(true)}
      />

      <div className="flex-1 flex overflow-hidden">
        <ProspectusSidebar
          prospectuses={prospectuses}
          activeProspectusId={activeProspectusId}
          onSelectProspectus={handleSelectProspectus}
        />

        <div className="flex-1">
          <ChatInterface activeProspectusId={activeProspectusId} />
        </div>
      </div>

      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUploadComplete={handleUploadComplete}
      />
    </div>
  );
}
