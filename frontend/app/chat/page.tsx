/**
 * Chat Page
 *
 * Main chat interface after login
 */
'use client'

import {useState, useEffect} from 'react';
import Header from '@/components/Header';
import ChatInterface from '@/components/ChatInterface';
import { getCurrentUser } from '@/lib/api';

export default function ChatPage() {
  const [username, setUsername] = useState<string>('');
  useEffect(() => {
    const fetchUser = async () => {
      try {
        const user = await getCurrentUser();
        setUsername(user.username);
      } catch (error) {
        console.error('Failed to get user', error);
      }
    };
    fetchUser();
  }, []);
  
  return (
    <div className="h-screen flex flex-col">
      <Header showLogout={true} username={username} />
      <ChatInterface />
    </div>
  );
}
