/**
 * ChatInterface Component
 *
 * Main chat interface that combines all chat-related components
 */

'use client';

import { useState, useEffect } from 'react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import { sendChatMessage, getChatHistory } from '@/lib/api';
import type { ChatMessage } from '@/types';

interface ChatInterfaceProps {
  activeProspectusId: string | null;
  onProspectusChange?: (prospectusId: string) => void;
}

export default function ChatInterface({ activeProspectusId, onProspectusChange }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Load chat history when prospectus is selected
  useEffect(() => {
    if (activeProspectusId) {
      loadChatHistory(activeProspectusId);
    } else {
      setMessages([]);
    }
  }, [activeProspectusId]);

  const loadChatHistory = async (prospectusId: string) => {
    try {
      const response = await getChatHistory(prospectusId);
      setMessages(response.messages);
    } catch (error){
      console.error('Failed to get chat history', error);
      setMessages([]);
    }
  };

  const handleSendMessage = async (messageText: string) => {
    if (!activeProspectusId) {
      alert('Please select a prospectus first');
      return;
    }
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString(),
      prospectus_id: activeProspectusId
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    try {
      const response = await sendChatMessage(messageText);
      setMessages(prev => [...prev, response])
    } catch (error) {
      console.error('Failed to send message', error)
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Chat Header */}
      <div className="bg-white border-b px-4 py-3">
        <h2 className="text-lg font-semibold">
          {activeProspectusId ? 'Chat with CMO Analyst' : 'Select a prospectus to begin'}
        </h2>
      </div>

      {/* Messages Area */}
      {activeProspectusId ? (
        <>
          <MessageList messages={messages} />
          <MessageInput
            onSendMessage={handleSendMessage}
            disabled={isLoading}
            placeholder={
              isLoading
                ? 'Agent is thinking...'
                : 'Ask a question about the prospectus...'
            }
          />
        </>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-500">
          <p>Select a prospectus from the sidebar or upload a new one to start chatting</p>
        </div>
      )}
    </div>
  );
}
