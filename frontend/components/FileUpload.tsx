/**
 * FileUpload Component
 *
 * Drag-and-drop file upload for prospectus PDFs
 */

'use client';

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadProspectus, getProspectusStatus } from '@/lib/api';
import { validatePdfFile, getStatusText, getStatusColor } from '@/lib/utils';
import type { UploadResponse } from '@/types';

interface FileUploadProps {
  onUploadComplete?: (prospectusId: string) => void;
}

export default function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [error, setError] = useState<string>('');

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    /**
     * TODO: Implement file upload logic
     *
     * Steps:
     * 1. Get the first file from acceptedFiles
     * 2. Validate the file using validatePdfFile()
     * 3. If valid, call uploadProspectus(file)
     * 4. Show upload progress
     * 5. Start polling getProspectusStatus() to track parsing progress
     * 6. When status is 'completed', call onUploadComplete()
     * 7. Handle errors appropriately
     *
     * Example polling logic:
     * const pollStatus = async (prospectusId: string) => {
     *   const interval = setInterval(async () => {
     *     const { status } = await getProspectusStatus(prospectusId);
     *     setUploadStatus(status);
     *     if (status === 'completed' || status === 'failed') {
     *       clearInterval(interval);
     *       if (status === 'completed') {
     *         onUploadComplete?.(prospectusId);
     *       }
     *     }
     *   }, 2000); // Poll every 2 seconds
     * };
     */
    console.log('TODO: Implement file upload:', acceptedFiles);
  }, [onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
    },
    maxFiles: 1,
    disabled: isUploading,
  });

  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
          ${isUploading ? 'cursor-not-allowed opacity-50' : ''}
        `}
      >
        <input {...getInputProps()} />

        {isUploading ? (
          <div className="space-y-2">
            <div className="text-lg font-semibold">Uploading and parsing...</div>
            <div className={`text-sm ${getStatusColor(uploadStatus)}`}>
              {getStatusText(uploadStatus)}
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              stroke="currentColor"
              fill="none"
              viewBox="0 0 48 48"
            >
              <path
                d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <div className="text-lg font-semibold">
              {isDragActive ? 'Drop the PDF here' : 'Drop a PDF here, or click to select'}
            </div>
            <p className="text-sm text-gray-500">CMO Prospectus PDF (Max 50MB)</p>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
