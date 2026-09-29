import React, { useState } from 'react';
import { Mail, Copy, Check, X, ExternalLink, ShieldCheck, Send } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

export default function ContactUsModal({ isOpen, onClose }) {
  const { t } = useLanguage();
  const [copiedEmail, setCopiedEmail] = useState('');
  const [openingEmail, setOpeningEmail] = useState('');

  if (!isOpen) return null;

  const contacts = [
    {
      name: 'Suriya Prakash S',
      department: 'ECE Department',
      email: 'suriyaprakash.s2025ece@sece.ac.in',
      role: 'CloudOps LLM Core Developer'
    },
    {
      name: 'Prajit R',
      department: 'AI & Data Science',
      email: 'prajit.r2025aids@sece.ac.in',
      role: 'AI Infrastructure Specialist'
    }
  ];

  const handleCopy = (email) => {
    navigator.clipboard.writeText(email);
    setCopiedEmail(email);
    setTimeout(() => setCopiedEmail(''), 2000);
  };

  const handleOpenMailClient = (email) => {
    setOpeningEmail(email);
    // Redirect to default OS mail client (Outlook, Mail, Thunderbird, Gmail handler)
    window.location.href = `mailto:${email}?subject=CloudOps%20LLM%20Support%20Inquiry`;
    setTimeout(() => setOpeningEmail(''), 2500);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl border border-slate-200 shadow-2xl max-w-md w-full p-6 space-y-5 animate-in zoom-in-95 duration-200">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 shadow-xs">
              <Mail className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-base text-slate-900">{t('contactTitle')}</h3>
              <p className="text-xs text-slate-500 font-medium">{t('contactSubtitle')}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Feedback Alert Toast */}
        {copiedEmail && (
          <div className="p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold flex items-center space-x-2 animate-in fade-in">
            <Check className="w-4 h-4 text-emerald-600" />
            <span>{t('copiedText')}</span>
          </div>
        )}

        {openingEmail && (
          <div className="p-2.5 rounded-xl bg-blue-50 border border-blue-200 text-blue-800 text-xs font-bold flex items-center space-x-2 animate-in fade-in">
            <Send className="w-4 h-4 text-blue-600 animate-pulse" />
            <span>{t('openingMail')}</span>
          </div>
        )}

        {/* Contact Email Cards */}
        <div className="space-y-3.5">
          {contacts.map((contact, idx) => (
            <div
              key={idx}
              className="p-4.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-3 hover:border-blue-300 transition-all shadow-xs"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-bold text-sm text-slate-900">{contact.name}</h4>
                  <span className="text-[11px] text-slate-500 font-semibold">{contact.role} ({contact.department})</span>
                </div>
                <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              </div>

              {/* Email Address & Actions */}
              <div className="bg-white p-3 rounded-xl border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                <a
                  href={`mailto:${contact.email}`}
                  onClick={(e) => {
                    e.preventDefault();
                    handleOpenMailClient(contact.email);
                  }}
                  className="font-mono text-blue-700 font-bold hover:underline truncate max-w-[220px]"
                  title="Click to Send Mail"
                >
                  {contact.email}
                </a>

                <div className="flex items-center space-x-1.5 shrink-0">
                  <button
                    onClick={() => handleCopy(contact.email)}
                    className="px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-[11px] transition-colors flex items-center space-x-1"
                    title="Copy Email ID"
                  >
                    {copiedEmail === contact.email ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                    <span>{copiedEmail === contact.email ? 'Copied' : t('copyEmail')}</span>
                  </button>

                  <button
                    onClick={() => handleOpenMailClient(contact.email)}
                    className="px-2.5 py-1 rounded-lg bg-black hover:bg-zinc-800 text-white font-bold text-[11px] transition-all shadow-xs flex items-center space-x-1 cursor-pointer"
                    title="Open OS Mail Client"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>{t('openMailClient')}</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Footer info */}
        <div className="pt-2 text-center text-xs text-slate-500 border-t border-slate-100">
          <span>Official Support Email Domain: <strong className="text-slate-800 font-mono">sece.ac.in</strong></span>
        </div>
      </div>
    </div>
  );
}
