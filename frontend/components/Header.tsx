/**
 * Header Component
 *
 * App header with title and logout button
 */

'use client';

import { useRouter } from 'next/navigation';
import { logout } from '@/lib/api';

interface HeaderProps {
  showLogout?: boolean;
  username?: string;
}

export default function Header({ showLogout, username }: HeaderProps) {
  const router = useRouter();

  const handleLogout = async () => {
    /**
     * TODO: Implement logout logic
     *
     * Steps:
     * 1. Call logout() from API client
     * 2. Redirect to home page
     *
     * Example:
     * await logout();
     * router.push('/');
     */
    console.log('TODO: Implement logout');
  };

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">CMO Analyst Agent</h1>
          <p className="text-sm text-gray-500">Prospectus Parsing & Analysis</p>
        </div>

        {showLogout && (
          <div className="flex items-center gap-4">
            {username && (
              <span className="text-sm text-gray-600">
                Logged in as: <span className="font-semibold">{username}</span>
              </span>
            )}
            <button
              onClick={handleLogout}
              className="px-4 py-2 text-sm text-gray-700 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
