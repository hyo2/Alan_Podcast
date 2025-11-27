// src/components/DocumentCard.tsx
import { FileText, MoreVertical, Star } from 'lucide-react';

interface DocumentCardProps {
  title: string;
  preview: string;
  date: string;
  starred?: boolean;
}

export default function DocumentCard({ title, preview, date, starred }: DocumentCardProps) {
  return (
    <div className="card-alan cursor-pointer">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-alan-gradient flex items-center justify-center">
            <FileText className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <p className="text-xs text-gray-500">{date}</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button className={`p-1.5 rounded-lg transition-colors ${
            starred ? 'text-yellow-500 hover:bg-yellow-50' : 'text-gray-400 hover:bg-gray-100'
          }`}>
            <Star className="w-4 h-4" fill={starred ? 'currentColor' : 'none'} />
          </button>
          <button className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100">
            <MoreVertical className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      <p className="text-sm text-gray-600 line-clamp-2">
        {preview}
      </p>
      
      <div className="mt-4 flex gap-2">
        <span className="px-3 py-1 bg-purple-50 text-purple-600 text-xs font-medium rounded-full">
          PDF
        </span>
        <span className="px-3 py-1 bg-blue-50 text-blue-600 text-xs font-medium rounded-full">
          AI 요약 완료
        </span>
      </div>
    </div>
  );
}