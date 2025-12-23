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
  const router = useRouter();

  const handleLogin = async () => {
    /**
     * TODO: Implement login logic
     *
     * Steps:
     * 1. Set isLoading to true
     * 2. Call login() from API client
     * 3. On success, redirect to /chat
     * 4. On error, show error message
     * 5. Set isLoading to false
     *
     * Example:
     * setIsLoading(true);
     * try {
     *   const { user, token } = await login();
     *   console.log('Logged in as:', user);
     *   router.push('/chat');
     * } catch (error) {
     *   console.error('Login failed:', error);
     *   alert('Login failed');
     * } finally {
     *   setIsLoading(false);
     * }
     */
    console.log('TODO: Implement login');
  };

  return (
    <button
      onClick={handleLogin}
      disabled={isLoading}
      className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed transition-colors"
    >
      {isLoading ? 'Logging in...' : 'Login as testuser'}
    </button>
  );
}
