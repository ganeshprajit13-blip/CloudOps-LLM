import React, { useEffect, useState } from 'react';
import {
  History as HistoryIcon,
  ThumbsUp,
  ThumbsDown,
  CheckCircle2,
  Sparkles,
  MessageSquare,
  Send,
  Eye,
  X
} from 'lucide-react';
import { troubleshootingApi } from '../api/troubleshootingApi';
import { formatDate, getStatusBadgeClass } from '../utils/formatters';
import LoadingSpinner from '../components/LoadingState';
import AIAnalysis from '../components/AIAnalysis';

export default function History() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAnalysis, setSelectedAnalysis] = useState(null);
  const [activeFeedbackId, setActiveFeedbackId] = useState(null);
  const [feedbackType, setFeedbackType] = useState('Correct');
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackSubmittedMsg, setFeedbackSubmittedMsg] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const res = await troubleshootingApi.getHistory();
        setHistory(res || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleFeedbackSubmit = async (analysisId) => {
    await troubleshootingApi.submitFeedback(analysisId, feedbackType, feedbackComment);
    setHistory((prev) =>
      prev.map((item) =>
        item.id === analysisId
          ? { ...item, userFeedback: feedbackType, feedbackComment: feedbackComment }
          : item
      )
    );
    setFeedbackSubmittedMsg(`Feedback recorded for diagnosis ${analysisId}`);
    setTimeout(() => setFeedbackSubmittedMsg(''), 3000);
    setActiveFeedbackId(null);
    setFeedbackComment('');
  };

  if (loading) return <LoadingSpinner message="Loading AI Diagnosis History..." />;

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* PAGE HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <h1 className="text-3xl sm:text-[34px] font-bold text-[#0F172A] tracking-tight">
              AI Diagnosis History
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD] text-xs font-semibold shrink-0">
              Evaluations & Feedback
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[#64748B] font-normal">
            Historical LLM root cause evaluations & admin feedback loops
          </p>
        </div>

        {feedbackSubmittedMsg && (
          <div className="px-4 py-2 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-bold animate-in fade-in shadow-xs">
            {feedbackSubmittedMsg}
          </div>
        )}
      </div>

      {/* History Table */}
      <div className="bg-white rounded-2xl border border-[#E2E8F0] overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F8FAFC] text-[#475569] uppercase tracking-wider font-semibold border-b border-[#E2E8F0]">
              <tr>
                <th className="px-6 py-3.5">Date & Time</th>
                <th className="px-6 py-3.5">Problem Statement</th>
                <th className="px-6 py-3.5">Service</th>
                <th className="px-6 py-3.5">Diagnosed Root Cause</th>
                <th className="px-6 py-3.5">AI Confidence</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5 text-center">Feedback</th>
                <th className="px-6 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {history.map((item) => (
                <tr key={item.id} className="hover:bg-[#F8FAFC] transition-colors">
                  <td className="px-6 py-4 text-[#64748B] whitespace-nowrap">
                    {formatDate(item.date)}
                  </td>

                  <td className="px-6 py-4 font-bold text-[#0F172A] max-w-xs truncate">
                    {item.problem}
                  </td>

                  <td className="px-6 py-4 font-semibold text-[#0284C7]">
                    {item.service}
                  </td>

                  <td className="px-6 py-4 text-[#64748B] max-w-sm truncate font-medium">
                    {item.probableCause}
                  </td>

                  <td className="px-6 py-4">
                    <span className="font-bold text-[#0284C7]">{item.confidence}%</span>
                  </td>

                  <td className="px-6 py-4">
                    <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${getStatusBadgeClass(item.status)}`}>
                      {item.status}
                    </span>
                  </td>

                  <td className="px-6 py-4 text-center">
                    {item.userFeedback ? (
                      <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold inline-flex items-center space-x-1 border ${
                        item.userFeedback === 'Correct'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-rose-50 text-rose-700 border-rose-200'
                      }`}>
                        {item.userFeedback === 'Correct' ? <ThumbsUp className="w-3 h-3" /> : <ThumbsDown className="w-3 h-3" />}
                        <span>{item.userFeedback}</span>
                      </span>
                    ) : (
                      <button
                        onClick={() => setActiveFeedbackId(activeFeedbackId === item.id ? null : item.id)}
                        className="px-3 py-1 rounded-xl bg-[#F0F7FF] hover:bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD] text-xs font-semibold transition-colors"
                      >
                        Rate Diagnosis
                      </button>
                    )}
                  </td>

                  <td className="px-6 py-4 text-right">
                    <button
                      onClick={() =>
                        setSelectedAnalysis({
                          problem: item.problem,
                          probableRootCause: item.probableCause,
                          confidence: item.confidence,
                          evidence: [
                            { label: 'CloudWatch Telemetry', value: 'Verified', status: 'pass' },
                            { label: 'Security Group rule', value: 'Check completed', status: 'fail' }
                          ],
                          recommendedAction: 'Apply recommended fix in infrastructure repository.',
                          impact: 'Production impact resolved.'
                        })
                      }
                      className="p-2 rounded-xl bg-[#F0F7FF] hover:bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD]/80 transition-colors"
                      title="Open full diagnosis details"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Rating & Feedback Form Modal/Drawer */}
      {activeFeedbackId && (
        <div className="bg-white p-6 sm:p-7 rounded-3xl border border-[#BAE6FD] shadow-2xl max-w-lg mx-auto space-y-4 animate-in slide-in-from-bottom-2">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
            <h3 className="text-xs font-bold text-[#0F172A] uppercase tracking-wider flex items-center space-x-2">
              <MessageSquare className="w-4 h-4 text-[#0284C7]" />
              <span>Was this diagnosis helpful?</span>
            </h3>
            <button onClick={() => setActiveFeedbackId(null)} className="text-[#64748B] hover:text-[#0F172A]">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center justify-center space-x-4 pt-2">
            <button
              onClick={() => setFeedbackType('Correct')}
              className={`flex-1 py-3 rounded-2xl border font-semibold text-xs flex items-center justify-center space-x-2 transition-all ${
                feedbackType === 'Correct'
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-300 font-bold shadow-xs'
                  : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]'
              }`}
            >
              <ThumbsUp className="w-4 h-4" />
              <span>👍 Correct Diagnosis</span>
            </button>

            <button
              onClick={() => setFeedbackType('Incorrect')}
              className={`flex-1 py-3 rounded-2xl border font-semibold text-xs flex items-center justify-center space-x-2 transition-all ${
                feedbackType === 'Incorrect'
                  ? 'bg-rose-50 text-rose-700 border-rose-300 font-bold shadow-xs'
                  : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]'
              }`}
            >
              <ThumbsDown className="w-4 h-4" />
              <span>👎 Incorrect Diagnosis</span>
            </button>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-[#0F172A] uppercase tracking-wider block">Additional feedback:</label>
            <textarea
              rows={3}
              value={feedbackComment}
              onChange={(e) => setFeedbackComment(e.target.value)}
              placeholder="Provide comments to improve the RAG vector store & LLM fine-tuning..."
              className="w-full p-3 rounded-xl bg-[#F0F7FF] border border-[#BAE6FD] text-[#0F172A] text-xs font-medium focus:outline-none focus:border-[#0284C7]"
            />
          </div>

          <button
            onClick={() => handleFeedbackSubmit(activeFeedbackId)}
            className="w-full py-2.5 rounded-xl bg-[#0284C7] hover:bg-[#0369A1] text-white font-bold text-xs shadow-xs transition-all flex items-center justify-center space-x-2 border border-[#0284C7]/20"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Submit Feedback to Backend API</span>
          </button>
        </div>
      )}

      {/* Selected Historical Analysis Viewer Modal */}
      {selectedAnalysis && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white p-6 sm:p-7 rounded-3xl border border-[#BAE6FD] max-w-4xl w-full max-h-[90vh] overflow-y-auto space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <span className="text-xs font-bold text-[#0284C7] uppercase tracking-wider">Historical AI Analysis View</span>
              <button onClick={() => setSelectedAnalysis(null)} className="p-1 text-[#64748B] hover:text-[#0F172A]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <AIAnalysis data={selectedAnalysis} />
          </div>
        </div>
      )}
    </div>
  );
}
