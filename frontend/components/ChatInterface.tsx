/**
 * ChatInterface Component
 *
 * Main chat interface that combines all chat-related components
 */

'use client';

import { useState, useEffect } from 'react';
import MessageList from './MessageList';
import MessageInput from './MessageInput';
import FileUpload from './FileUpload';
import { sendChatMessage, getChatHistory } from '@/lib/api';
import type { ChatMessage } from '@/types';

export default function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentProspectusId, setCurrentProspectusId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Load chat history when prospectus is selected
  useEffect(() => {
    if (currentProspectusId) {
      loadChatHistory(currentProspectusId);
    }
  }, [currentProspectusId]);

  const loadChatHistory = async (prospectusId: string) => {
    /**
     * Steps:
     * 1. Call getChatHistory(prospectusId)
     * 2. Set messages state with history
     * 3. Handle errors
     *
     */
    try {
      const response = await getChatHistory(prospectusId);
      setMessages(prev => [...prev, ...response.messages]);
    } catch (error){
      console.error('failed to get chat history', error);
    }
  };

  const handleUploadComplete = (prospectusId: string) => {
    /**
     * Steps:
     * 1. Set currentProspectusId to the uploaded prospectus
     * 2. Add a system message to chat: "Prospectus uploaded and parsed successfully. You can now ask questions."
     * 3. Load chat history (if any)
     */
    
    const systemMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'system',
      content: 'Prospectus uploaded and parsed successfully. You can now ask questions.',
      timestamp: new Date().toISOString()
    };
    setMessages([systemMessage]);
    setCurrentProspectusId(prospectusId);
  };

  const handleSendMessage = async (messageText: string) => {
    /**
     * Steps:
     * 1. Check if currentProspectusId exists
     * 2. Add user message to messages state
     * 3. Set isLoading to true
     * 4. Call sendChatMessage(currentProspectusId, messageText)
     * 5. Add agent response to messages state
     * 6. Set isLoading to false
     * 7. Handle errors
     */
    if (!currentProspectusId) {
      alert('Please upload a prospectus first');
      return;
    }
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString(),
      prospectus_id: currentProspectusId
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    try {
      const response = await sendChatMessage(currentProspectusId, messageText);
      setMessages(prev => [...prev, response])
    } catch (error) {
      console.error('failed to send message', error)
    } finally {
      setIsLoading(false);
    }
    
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Upload Area - Show if no prospectus selected */}
      {!currentProspectusId && (
        <div className="p-8 bg-white border-b">
          <h2 className="text-xl font-semibold mb-4">Upload a Prospectus to Begin</h2>
          <FileUpload onUploadComplete={handleUploadComplete} />
        </div>
      )}

      {/* Chat Area - Show if prospectus selected */}
      {currentProspectusId && (
        <>
          <div className="bg-white border-b px-4 py-3">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold">Chat with CMO Analyst</h2>
              <button
                onClick={() => setCurrentProspectusId(null)}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Upload New Prospectus
              </button>
            </div>
          </div>

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
      )}
    </div>
  );
}
