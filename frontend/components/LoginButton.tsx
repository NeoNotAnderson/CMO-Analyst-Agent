/**
 * LoginButton Component
 *
 * Simple mock login button for testuser
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { login } from '@/lib/api';

export default function LoginButton() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleLogin = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const { user, token } = await login();
      console.log('Logged in as:', user);
      
      // Store user data in localStorage (optional)
      localStorage.setItem('user', JSON.stringify(user));
      
      // Redirect to chat page
      router.push('/chat');
    } catch (error) {
      console.error('Login failed:', error);
      const errorMessage = error instanceof Error ? error.message : 'Login failed';
      setError(errorMessage);
      alert(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <button
        onClick={handleLogin}
        disabled={isLoading}
        className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed transition-colors"
      >
        {isLoading ? 'Logging in...' : 'Login as testuser'}
      </button>
      
      {error && (
        <p className="mt-2 text-red-600 text-sm">{error}</p>
      )}
    </div>
  );
}
