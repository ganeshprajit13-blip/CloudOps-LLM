import React, { useEffect, useState } from 'react';
import {
  CreditCard,
  DollarSign,
  TrendingUp,
  AlertTriangle,
  Download,
  Sparkles,
  PieChart as PieChartIcon,
  BarChart3,
  FileText
} from 'lucide-react';
import {
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer
} from 'recharts';
import { billingApi } from '../api/billingApi';
import LoadingSpinner from '../components/LoadingState';
import { useLanguage } from '../context/LanguageContext';

export default function Billing() {
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const { t } = useLanguage();

  useEffect(() => {
    async function load() {
      try {
        const res = await billingApi.getBillingData();
        setBilling(res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) return <LoadingSpinner message="Fetching AWS Billing & Cost Telemetry..." />;

  const { summary, byService, dailyCosts, anomalies, invoices } = billing || {};

  const budgetPercent = Math.round((summary?.monthlySpend / summary?.budgetLimit) * 100);

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Page Header (Monochromatic Primary System) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl lg:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
            {t('billingTitle')}
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Real-time AWS Cost Explorer metrics, budget alerts & AI cost anomaly advisor
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button className="px-4 py-2.5 rounded-xl bg-black hover:bg-zinc-800 text-white text-xs font-bold shadow-sm transition-all flex items-center space-x-2 cursor-pointer">
            <Download className="w-4 h-4 text-white" />
            <span>Export Cost Report (CSV)</span>
          </button>
        </div>
      </div>

      {/* 1. Summary KPI Cards (Monochromatic Blue Surfaces) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Monthly Spend */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-600 uppercase tracking-wider">
            <span>{t('mtdSpend')}</span>
            <DollarSign className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl lg:text-3xl font-black text-slate-900">
              ${summary?.monthlySpend?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </span>
            <span className="text-xs text-slate-500 font-bold">/ ${summary?.budgetLimit}</span>
          </div>
          {/* Progress bar */}
          <div className="space-y-1">
            <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden border border-slate-200">
              <div
                className="h-full rounded-full bg-blue-600"
                style={{ width: `${budgetPercent}%` }}
              />
            </div>
            <div className="flex justify-between text-[11px] text-slate-600 font-bold">
              <span>{budgetPercent}% of monthly budget used</span>
              <span>{summary?.period}</span>
            </div>
          </div>
        </div>

        {/* Projected Spend */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-600 uppercase tracking-wider">
            <span>{t('forecastedSpend')}</span>
            <TrendingUp className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl lg:text-3xl font-black text-slate-900">
              ${summary?.projectedSpend?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </span>
          </div>
          <p className="text-xs text-slate-600 font-semibold">
            Projected within budget by <strong className="text-blue-700">${summary?.budgetLimit - summary?.projectedSpend}</strong>
          </p>
        </div>

        {/* AI Savings Opportunities */}
        <div className="bg-white p-5 rounded-2xl border border-blue-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-blue-800 uppercase tracking-wider">
            <span>{t('aiSavings')}</span>
            <Sparkles className="w-4 h-4 text-blue-600" />
          </div>
          <div className="flex items-baseline space-x-2">
            <span className="text-2xl lg:text-3xl font-black text-blue-950">
              {summary?.savingsOpportunitiesCount} Recommendations
            </span>
          </div>
          <p className="text-xs text-blue-800 font-bold">
            Est. potential savings: <strong className="text-blue-700">$41.70 / mo</strong>
          </p>
        </div>

        {/* Active AWS Account */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-3">
          <div className="flex items-center justify-between text-xs font-bold text-slate-600 uppercase tracking-wider">
            <span>{t('paymentMethod')}</span>
            <CreditCard className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-sm font-extrabold text-slate-900">
            AWS Invoicing (Visa •••• 4092)
          </div>
          <span className="inline-block px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-800 text-[10px] font-bold border border-blue-200">
            Auto-Pay Enabled
          </span>
        </div>
      </div>

      {/* 2. Charts Row: Service Breakdown & Daily Trend */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Service Cost Breakdown */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
              <PieChartIcon className="w-4 h-4 text-blue-600" />
              <span>Cost Allocation by AWS Service</span>
            </h3>
            <span className="text-xs font-bold text-slate-600">September 2026</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-center">
            <div className="h-48 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={byService}
                    dataKey="cost"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={75}
                    innerRadius={45}
                  >
                    {byService?.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => `$${value}`} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="space-y-2 text-xs">
              {byService?.map((s, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="flex items-center space-x-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                    <span className="font-bold text-slate-800">{s.name}</span>
                  </div>
                  <div className="text-right font-black text-slate-900">
                    ${s.cost} <span className="text-[10px] text-slate-500 font-medium">({s.percentage}%)</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Daily Cost Trend */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
              <BarChart3 className="w-4 h-4 text-blue-600" />
              <span>Daily AWS Spend Trend ($ USD)</span>
            </h3>
            <span className="text-xs font-bold text-slate-600">Last 8 Days</span>
          </div>

          <div className="h-52 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailyCosts}>
                <defs>
                  <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#2563eb" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" stroke="#475569" fontSize={11} tickLine={false} />
                <YAxis stroke="#475569" fontSize={11} tickLine={false} domain={[80, 'auto']} />
                <Tooltip formatter={(value) => `$${value}`} />
                <Area type="monotone" dataKey="cost" stroke="#2563eb" strokeWidth={2.5} fillOpacity={1} fill="url(#costGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* 3. Cost Anomaly Detection Alerts */}
      <div className="bg-white p-6 rounded-2xl border border-blue-200 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-blue-600" />
            <span>AI Cost Anomaly & Waste Detector</span>
          </h3>
          <span className="px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-800 text-xs font-bold border border-blue-200">
            {anomalies?.length} Anomalies Flagged
          </span>
        </div>

        <div className="space-y-3">
          {anomalies?.map((anom) => (
            <div key={anom.id} className="p-4 rounded-xl bg-blue-50/40 border border-blue-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="font-extrabold text-slate-900">{anom.title}</span>
                  <span className="px-2 py-0.2 rounded bg-blue-100 text-blue-800 text-[10px] font-bold">{anom.service}</span>
                </div>
                <p className="text-slate-700 font-medium">
                  <strong className="text-slate-900">AI Advisor Recommendation:</strong> {anom.aiRecommendation}
                </p>
              </div>

              <div className="shrink-0 text-right">
                <span className="text-sm font-black text-blue-900 block">{anom.impact}</span>
                <span className="text-[10px] text-slate-500 font-bold">Extra Expense</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 4. Invoice History Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center space-x-2">
            <FileText className="w-4 h-4 text-blue-600" />
            <span>Monthly AWS Invoice Statements</span>
          </h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-700 uppercase tracking-wider font-bold border-b border-slate-200">
              <tr>
                <th className="px-6 py-3.5">Invoice ID</th>
                <th className="px-6 py-3.5">Billing Period</th>
                <th className="px-6 py-3.5">Billed Amount</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5">Payment Date</th>
                <th className="px-6 py-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {invoices?.map((inv) => (
                <tr key={inv.id} className="hover:bg-blue-50/40 transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-blue-700">{inv.id}</td>
                  <td className="px-6 py-4 font-bold text-slate-900">{inv.period}</td>
                  <td className="px-6 py-4 font-black text-slate-900">{inv.amount}</td>
                  <td className="px-6 py-4">
                    <span className="px-2.5 py-1 rounded-full bg-blue-50 text-blue-800 font-bold border border-blue-200 text-[11px]">
                      {inv.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-600 font-medium">{inv.date}</td>
                  <td className="px-6 py-4 text-right">
                    <button className="px-3 py-1.5 rounded-xl bg-blue-50 hover:bg-blue-100 text-xs font-bold text-blue-700 transition-colors inline-flex items-center space-x-1 border border-blue-200">
                      <Download className="w-3.5 h-3.5" />
                      <span>Download PDF</span>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
