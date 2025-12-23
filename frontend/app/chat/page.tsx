/**
 * Chat Page
 *
 * Main chat interface after login
 */

import Header from '@/components/Header';
import ChatInterface from '@/components/ChatInterface';

export default function ChatPage() {
  return (
    <div className="h-screen flex flex-col">
      <Header showLogout={true} username="testuser" />
      <ChatInterface />
    </div>
  );
}
