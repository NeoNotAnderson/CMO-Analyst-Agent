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
import { getCurrentUser, initializeSession, getProspectusList, setActiveProspectus, resumeParsing } from '@/lib/api';
import { useProspectusStatusPolling } from '@/hooks/useProspectusStatusPolling';
import ParsingResumeDialog from '@/components/ParsingResumeDialog';
import type { Prospectus } from '@/types';

export default function ChatPage() {
  const [username, setUsername] = useState<string>('');
  const [prospectuses, setProspectuses] = useState<Prospectus[]>([]);
  const [activeProspectusId, setActiveProspectusId] = useState<string | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [parsingDialog, setParsingDialog] = useState<{
    prospectusId: string;
    prospectusName: string;
    parsingMessage: string;
  } | null>(null);
  const [parsingInProgress, setParsingInProgress] = useState<string | null>(null);

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
    try {
      const data = await setActiveProspectus(prospectusId);
      if (data.needs_parsing) {
        // Don't set activeProspectusId yet — wait for user to confirm or cancel
        setParsingDialog({
          prospectusId,
          prospectusName: data.prospectus_name,
          parsingMessage: data.parsing_message ?? 'This prospectus has not been fully parsed yet.',
        });
      } else {
        setActiveProspectusId(prospectusId);
      }
    } catch (error) {
      console.error('Failed to set active prospectus in backend:', error);
    }
  };

  const handleResumeParsingConfirm = async () => {
    if (!parsingDialog) return;
    const { prospectusId } = parsingDialog;
    setParsingDialog(null);
    setActiveProspectusId(prospectusId);
    setParsingInProgress(prospectusId);
    try {
      await resumeParsing(prospectusId);
    } catch (error) {
      console.error('Failed to resume parsing:', error);
      setParsingInProgress(null);
    }
  };

  const handleResumeParsingCancel = () => {
    // User declined — leave activeProspectusId unchanged (previous selection or null)
    setParsingDialog(null);
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
      // Clear parsingInProgress if the tracked prospectus has finished
      setParsingInProgress((current) => {
        if (!current) return null;
        const updated = updatedProspectuses.find((p) => p.prospectus_id === current);
        if (updated && (updated.parse_status === 'completed' || updated.parse_status === 'failed')) {
          return null;
        }
        return current;
      });
    } catch (error) {
      console.error('Failed to refresh prospectuses during polling', error);
    }
  }, []);

  // Only poll while a resume was explicitly triggered by the user
  useProspectusStatusPolling({
    prospectuses,
    onStatusUpdate: refreshProspectusList,
    enabled: !isLoading && parsingInProgress !== null,
  });

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <p className="text-gray-500">Loading session...</p>
      </div>
    );
  }

  const isParsingActive = parsingInProgress !== null && parsingInProgress === activeProspectusId;

  return (
    <div className="h-screen flex flex-col">
      <Header
        showLogout={true}
        username={username}
        onUploadClick={() => setIsUploadModalOpen(true)}
      />

      {isParsingActive && (
        <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 flex items-center gap-2 text-sm text-yellow-800">
          <svg className="animate-spin h-4 w-4 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Parsing in progress — this may take 5–10 minutes. Deal-specific questions will be available once complete.
        </div>
      )}

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

      {parsingDialog && (
        <ParsingResumeDialog
          isOpen={true}
          prospectusName={parsingDialog.prospectusName}
          parsingMessage={parsingDialog.parsingMessage}
          onConfirm={handleResumeParsingConfirm}
          onCancel={handleResumeParsingCancel}
        />
      )}
    </div>
  );
}
