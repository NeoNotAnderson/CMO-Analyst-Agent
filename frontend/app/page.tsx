/**
 * Landing Page / Login Page
 *
 * Simple login page with mock authentication
 */

import Header from '@/components/Header';
import LoginButton from '@/components/LoginButton';

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="container mx-auto px-4 py-16">
        <div className="max-w-md mx-auto bg-white rounded-lg shadow-lg p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Welcome to CMO Analyst Agent
            </h1>
            <p className="text-gray-600">
              AI-powered prospectus parsing and analysis
            </p>
          </div>

          <div className="space-y-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="font-semibold text-blue-900 mb-2">Features:</h3>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• Upload CMO prospectus PDFs</li>
                <li>• Automatic parsing and structure extraction</li>
                <li>• Interactive chat interface</li>
                <li>• Question answering about your prospectus</li>
              </ul>
            </div>

            <div className="pt-4 flex justify-center">
              <LoginButton />
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-gray-200 text-center text-sm text-gray-500">
            <p>Demo Mode: Using testuser credentials</p>
          </div>
        </div>
      </main>
    </div>
  );
}
