import React, { useState, useRef, useEffect } from 'react';
import { Bot, Send, X, RefreshCw, Sparkles, User, HelpCircle, Copy, Check } from 'lucide-react';
import { askGroqSupport } from '../api/groqSupportApi';
import CloudOpsMark from './CloudOpsMark';

export default function SupportChatbotModal({ isOpen, onClose }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! 👋 I am your **CloudOps LLM AI Support Assistant** (Powered by Groq Llama 3.3). How can I assist you with your AWS infrastructure, FastAPI connection, or troubleshooting today?'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  if (!isOpen) return null;

  const handleSend = async (textToSend = input) => {
    if (!textToSend.trim() || loading) return;

    const userMsg = { role: 'user', content: textToSend };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput('');
    setLoading(true);

    try {
      // Format messages history for Groq API
      const apiHistory = newHistory.map(m => ({
        role: m.role,
        content: m.content
      }));

      const reply = await askGroqSupport(apiHistory);
      setMessages([...newHistory, { role: 'assistant', content: reply }]);
    } catch (err) {
      setMessages([
        ...newHistory,
        {
          role: 'assistant',
          content: 'I encountered a temporary connection issue reaching the Groq AI service. Please check your internet or try asking again.'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const samplePrompts = [
    'How do I configure the FastAPI backend IP?',
    'Why is my EC2 HTTPS port 443 blocked?',
    'How does RAG vector search work in CloudOps?'
  ];

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-xs flex items-center justify-end p-4 sm:p-6 animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl border border-slate-200 shadow-2xl w-full max-w-md h-[600px] max-h-[90vh] flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">

        {/* Chat Header */}
        <div className="bg-slate-900 text-white p-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-white border border-slate-200 flex items-center justify-center shrink-0 shadow-md p-1">
              <CloudOpsMark size={24} />
            </div>
            <div>
              <h3 className="font-bold text-sm leading-none text-white">CloudOps Support AI</h3>
              <p className="text-[10px] text-sky-400 font-mono mt-1 flex items-center space-x-1">


              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-xl hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Messages Body */}
        <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-slate-50">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex items-start space-x-2.5 ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''
                }`}
            >
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs shrink-0 font-bold ${msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-900 text-sky-400'
                  }`}
              >
                {msg.role === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
              </div>

              <div
                className={`p-3 rounded-2xl text-xs leading-relaxed max-w-[88%] shadow-xs ${msg.role === 'user'
                    ? 'bg-blue-600 text-white font-medium rounded-tr-none'
                    : 'bg-white border border-slate-200 text-slate-900 rounded-tl-none font-normal'
                  }`}
              >
                <FormattedMessage content={msg.content} role={msg.role} />
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex items-center space-x-2 p-3 bg-white border border-slate-200 rounded-2xl w-fit text-xs text-slate-500 font-medium">
              <RefreshCw className="w-3.5 h-3.5 text-blue-600 animate-spin" />
              <span>Groq AI is processing your support response...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Sample Prompts */}
        <div className="p-2.5 bg-white border-t border-slate-100 flex flex-wrap gap-1.5">
          {samplePrompts.map((prompt, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(prompt)}
              className="px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-[10.5px] font-medium text-slate-600 transition-colors"
            >
              {prompt}
            </button>
          ))}
        </div>

        {/* Input Footer */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="p-3 bg-white border-t border-slate-200 flex items-center space-x-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your support question..."
            className="flex-1 px-3.5 py-2 text-xs rounded-xl bg-slate-100 border border-slate-200 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-600 font-medium"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="p-2 rounded-xl bg-black hover:bg-zinc-800 disabled:opacity-50 text-white shadow-sm transition-all cursor-pointer"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}

function FormattedMessage({ content, role }) {
  if (!content) return null;

  if (role === 'user') {
    return <span className="whitespace-pre-wrap">{content}</span>;
  }

  // Clean raw HTML <br> or <br/> tags
  let cleaned = content.replace(/<br\s*\/?>/gi, '\n');

  // Split content into blocks (code blocks vs text/table blocks)
  const codeBlockRegex = /```(?:\w+)?\n?([\s\S]*?)```/g;
  const blocks = [];
  let lastIndex = 0;
  let match;

  while ((match = codeBlockRegex.exec(cleaned)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: 'text', text: cleaned.slice(lastIndex, match.index) });
    }
    blocks.push({ type: 'code', code: match[1] });
    lastIndex = codeBlockRegex.lastIndex;
  }
  if (lastIndex < cleaned.length) {
    blocks.push({ type: 'text', text: cleaned.slice(lastIndex) });
  }

  return (
    <div className="space-y-2 text-xs leading-relaxed">
      {blocks.map((block, bIdx) => {
        if (block.type === 'code') {
          return (
            <pre key={bIdx} className="bg-slate-900 text-sky-300 font-mono p-2.5 rounded-xl my-2 text-[11px] overflow-x-auto border border-slate-800 shadow-xs">
              <code>{block.code.trim()}</code>
            </pre>
          );
        }

        const lines = block.text.split('\n');
        const elements = [];
        let i = 0;

        while (i < lines.length) {
          const line = lines[i];
          const trimmed = line.trim();

          // Markdown table detection
          if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
            const tableRows = [];
            while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
              tableRows.push(lines[i].trim());
              i++;
            }

            const dataRows = tableRows.filter(r => !/^\|[\s\-:]+\|/.test(r.replace(/\s+/g, '')));
            if (dataRows.length > 0) {
              const parseCells = (rowStr) => rowStr.split('|').slice(1, -1).map(c => c.trim());
              const headers = parseCells(dataRows[0]);
              const bodyRows = dataRows.slice(1);

              elements.push(
                <div key={`tbl-${i}`} className="my-2.5 overflow-x-auto rounded-xl border border-slate-200 shadow-xs bg-white">
                  <table className="w-full text-left text-[11px] border-collapse">
                    <thead className="bg-slate-100 border-b border-slate-200 font-bold text-slate-800">
                      <tr>
                        {headers.map((h, hIdx) => (
                          <th key={hIdx} className="px-2.5 py-1.5 border-r border-slate-200 last:border-r-0">
                            {renderInlineMarkdown(h)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      {bodyRows.map((rStr, rIdx) => (
                        <tr key={rIdx} className="hover:bg-slate-50">
                          {parseCells(rStr).map((cell, cIdx) => (
                            <td key={cIdx} className="px-2.5 py-1.5 border-r border-slate-100 last:border-r-0 font-medium">
                              {renderInlineMarkdown(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            }
            continue;
          }

          // Headers
          if (trimmed.startsWith('#')) {
            const headerText = trimmed.replace(/^#+\s*/, '');
            elements.push(
              <h4 key={i} className="font-bold text-slate-900 text-xs mt-2 mb-1">
                {renderInlineMarkdown(headerText)}
              </h4>
            );
            i++;
            continue;
          }

          // Bullet lists
          if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || /^\d+\.\s/.test(trimmed)) {
            const listText = trimmed.replace(/^[-*\d.]+\s*/, '');
            elements.push(
              <div key={i} className="flex items-start space-x-1.5 my-1 pl-1">
                <span className="text-blue-600 font-bold select-none">•</span>
                <span className="flex-1">{renderInlineMarkdown(listText)}</span>
              </div>
            );
            i++;
            continue;
          }

          if (!trimmed) {
            i++;
            continue;
          }

          elements.push(
            <p key={i} className="my-1">
              {renderInlineMarkdown(line)}
            </p>
          );
          i++;
        }

        return <div key={bIdx}>{elements}</div>;
      })}
    </div>
  );
}

function renderInlineMarkdown(str) {
  if (!str) return '';
  const parts = str.split(/(\*\*.*?\*\*|`.*?`)/g);

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={index} className="bg-slate-100 text-blue-700 font-mono px-1.5 py-0.5 rounded text-[11px] font-semibold border border-slate-200">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}
