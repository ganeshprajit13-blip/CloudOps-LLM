import React, { useEffect, useState } from 'react';
import {
  BookOpen,
  Database,
  FileText,
  Search,
  CheckCircle2,
  ExternalLink,
  Layers,
  Clock,
  Eye,
  X,
  RefreshCw,
  Server
} from 'lucide-react';
import { knowledgeApi } from '../api/knowledgeApi';
import LoadingSpinner from '../components/LoadingState';

export default function KnowledgeBase() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  async function loadData() {
    try {
      const data = await knowledgeApi.getKnowledgeBase();
      setSources(data || []);
    } catch (err) {
      console.error('Failed to load Knowledge Base:', err);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const handleSearch = async (val) => {
    setSearch(val);
    if (!val.trim()) {
      loadData();
      return;
    }
    try {
      const results = await knowledgeApi.searchKnowledgeBase(val);
      setSources(results || []);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    loadData();
  };

  if (loading) return <LoadingSpinner message="Fetching RAG Vector Store Knowledge Index from Backend..." />;

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      
      {/* PAGE HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <h1 className="text-3xl sm:text-[34px] font-bold text-[#0F172A] tracking-tight">
              RAG Knowledge Base
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD] text-xs font-semibold flex items-center space-x-1.5 shrink-0">
              <Database className="w-3.5 h-3.5 text-[#0284C7]" />
              <span>Vector Store Connected</span>
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[#64748B] font-normal">
            Vector embeddings & retrieved AWS troubleshooting documentation indexed by backend API
          </p>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            title="Refresh Knowledge Index"
            className="p-2.5 rounded-xl bg-white border border-[#E2E8F0] text-[#0369A1] hover:text-[#0284C7] hover:border-[#BAE6FD] transition-colors shadow-xs"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>

          {/* Search Box */}
          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#0369A1]" />
            <input
              type="text"
              placeholder="Search RAG documents or vector topics..."
              value={search}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-xs rounded-xl bg-[#F0F7FF] border border-[#BAE6FD] text-[#0F172A] placeholder-[#0369A1]/60 focus:outline-none focus:border-[#0284C7] font-medium transition-colors"
            />
          </div>
        </div>
      </div>

      {/* GRID OF KNOWLEDGE SOURCES */}
      {sources.length === 0 ? (
        <div className="bg-white p-12 rounded-2xl border border-[#E2E8F0] text-center space-y-3">
          <BookOpen className="w-10 h-10 text-[#0369A1] mx-auto opacity-50" />
          <h3 className="text-base font-bold text-[#0F172A]">No Matching Knowledge Sources Found</h3>
          <p className="text-xs text-[#64748B]">Try searching for different AWS terms like EC2, VPC, Security Group, or CloudWatch.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sources.map((doc) => (
            <div
              key={doc.id}
              className="bg-white p-6 rounded-2xl border border-[#E2E8F0] shadow-xs hover:border-[#BAE6FD] transition-all duration-200 flex flex-col justify-between space-y-4 group"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="px-2.5 py-0.5 rounded-full bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD] text-[10px] font-semibold uppercase tracking-wider">
                    {doc.category}
                  </span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-semibold uppercase tracking-wider">
                    {doc.status}
                  </span>
                </div>

                <h3 className="text-base font-bold text-[#0F172A] group-hover:text-[#0284C7] transition-colors leading-snug">
                  {doc.title}
                </h3>

                <p className="text-xs text-[#64748B] leading-relaxed line-clamp-2">
                  {doc.description}
                </p>
              </div>

              <div className="pt-3 border-t border-[#E2E8F0] flex items-center justify-between text-xs text-[#64748B]">
                <div className="flex items-center space-x-3">
                  <span className="flex items-center space-x-1 font-mono text-[#0284C7] font-bold">
                    <Database className="w-3.5 h-3.5" />
                    <span>{doc.chunksCount} Chunks</span>
                  </span>
                  <span className="text-[11px]">{doc.lastUpdated}</span>
                </div>

                <button
                  onClick={() => setSelectedDoc(doc)}
                  className="p-2 rounded-xl bg-[#F0F7FF] hover:bg-[#E0F2FE] text-[#0284C7] transition-colors border border-[#BAE6FD]/80"
                  title="Inspect Vector Chunks"
                >
                  <Eye className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* CHUNK INSPECTOR MODAL */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white p-6 sm:p-7 rounded-3xl border border-[#BAE6FD] shadow-2xl max-w-2xl w-full space-y-5 animate-in zoom-in-95 duration-200">
            
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-[#E2E8F0] pb-4">
              <div>
                <span className="text-xs font-semibold text-[#0284C7] uppercase tracking-wider block mb-0.5">{selectedDoc.category}</span>
                <h3 className="text-lg font-bold text-[#0F172A]">{selectedDoc.title}</h3>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="p-1.5 rounded-xl hover:bg-[#F0F7FF] text-[#64748B] hover:text-[#0F172A] transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-[#64748B] bg-[#F8FAFC] p-3.5 rounded-xl border border-[#E2E8F0]">
                <span>Vector Index Chunks: <strong className="text-[#0284C7] font-bold">{selectedDoc.chunksCount}</strong></span>
                <span>Last Updated: <strong className="text-[#0F172A] font-bold">{selectedDoc.lastUpdated}</strong></span>
                <span>Status: <strong className="text-emerald-700 font-bold">{selectedDoc.status}</strong></span>
              </div>

              <div className="space-y-2">
                <span className="text-xs font-bold uppercase tracking-wider text-[#0F172A] block">Sample Vector Chunk Content:</span>
                <div className="p-4 rounded-2xl bg-[#F8FAFC] border border-[#E2E8F0] text-xs font-mono text-[#0F172A] leading-relaxed whitespace-pre-wrap">
                  {selectedDoc.sampleChunk}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setSelectedDoc(null)}
                className="px-4 py-2.5 rounded-xl bg-[#F0F7FF] hover:bg-[#E0F2FE] text-xs font-semibold text-[#0F172A] border border-[#BAE6FD] transition-colors"
              >
                Close Inspector
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
