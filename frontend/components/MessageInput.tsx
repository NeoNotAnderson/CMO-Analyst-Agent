/**
 * MessageInput Component
 *
 * Text input with send button for chat messages
 */

'use client';

import { useState, KeyboardEvent } from 'react';

interface MessageInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function MessageInput({ onSendMessage, disabled, placeholder }: MessageInputProps) {
  const [message, setMessage] = useState('');

  const handleSend = () => {
    /**
     * TODO: Implement send message logic
     *
     * Steps:
     * 1. Trim the message
     * 2. Check if message is not empty
     * 3. Call onSendMessage(message)
     * 4. Clear the input field
     *
     * Example:
     * const trimmed = message.trim();
     * if (trimmed) {
     *   onSendMessage(trimmed);
     *   setMessage('');
     * }
     */
    console.log('TODO: Implement send message:', message);
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    /**
     * TODO: Handle Enter key to send message
     *
     * Allow Shift+Enter for new line
     * Enter alone sends the message
     *
     * Example:
     * if (e.key === 'Enter' && !e.shiftKey) {
     *   e.preventDefault();
     *   handleSend();
     * }
     */
  };

  return (
    <div className="border-t bg-white p-4">
      <div className="flex gap-2">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={disabled}
          placeholder={placeholder || 'Type a message... (Enter to send, Shift+Enter for new line)'}
          className="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
          rows={3}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !message.trim()}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors self-end"
        >
          Send
        </button>
      </div>
    </div>
  );
}
