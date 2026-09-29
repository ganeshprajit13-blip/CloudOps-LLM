import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Server,
  Layers,
  Shield,
  Globe,
  Radio,
  Search,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  ExternalLink
} from 'lucide-react';
import { resourceApi } from '../api/resourceApi';
import { getStatusBadgeClass } from '../utils/formatters';
import LoadingSpinner from '../components/LoadingState';

const tabs = [
  { id: 'ec2', label: 'EC2 Instances', icon: Server },
  { id: 'vpc', label: 'VPCs & Subnets', icon: Layers },
  { id: 'securityGroups', label: 'Security Groups', icon: Shield },
  { id: 'loadBalancers', label: 'Load Balancers', icon: Globe },
  { id: 'cloudWatch', label: 'CloudWatch Alarms', icon: Radio },
];

export default function Resources() {
  const [searchParams] = useSearchParams();
  const initialSearch = searchParams.get('q') || '';

  const [activeTab, setActiveTab] = useState('ec2');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(initialSearch);

  useEffect(() => {
    const q = searchParams.get('q');
    if (q) setSearch(q);
  }, [searchParams]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await resourceApi.getResources(activeTab);
        setData(res || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [activeTab]);

  const filtered = data.filter((item) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return JSON.stringify(item).toLowerCase().includes(q);
  });

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* PAGE HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div className="space-y-1">
          <div className="flex items-center space-x-3">
            <h1 className="text-3xl sm:text-[34px] font-bold text-[#0F172A] tracking-tight">
              AWS Cloud Resources
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD] text-xs font-semibold shrink-0">
              Live Inventory
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[#64748B] font-normal">
            Real-time AWS EC2, VPC, ALB & CloudWatch resources fetched from backend
          </p>
        </div>

        {/* Search Input */}
        <div className="relative w-full sm:w-72 shrink-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#0369A1]" />
          <input
            type="text"
            placeholder="Filter resource ID or name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-xs rounded-xl bg-[#F0F7FF] border border-[#BAE6FD] text-[#0F172A] placeholder-[#0369A1]/60 focus:outline-none focus:border-[#0284C7] font-medium transition-colors"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center space-x-2 border-b border-[#E2E8F0] overflow-x-auto pb-3">
        {tabs.map((t) => {
          const Icon = t.icon;
          const isActive = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
                isActive
                  ? 'bg-[#E0F2FE] text-[#0284C7] border border-[#BAE6FD] font-bold shadow-xs'
                  : 'bg-white text-[#64748B] hover:text-[#0F172A] hover:bg-[#F0F7FF] border border-[#E2E8F0]'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-[#0284C7]' : 'text-[#64748B]'}`} />
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* Content Tables */}
      {loading ? (
        <LoadingSpinner message={`Querying FastAPI backend for AWS ${activeTab.toUpperCase()} resources...`} />
      ) : (
        <div className="bg-white rounded-2xl border border-[#E2E8F0] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            
            {/* 1. EC2 Table */}
            {activeTab === 'ec2' && (
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F8FAFC] text-[#475569] uppercase tracking-wider font-semibold border-b border-[#E2E8F0]">
                  <tr>
                    <th className="px-6 py-3.5">Instance ID</th>
                    <th className="px-6 py-3.5">Name Tag</th>
                    <th className="px-6 py-3.5">Status</th>
                    <th className="px-6 py-3.5">Instance Type</th>
                    <th className="px-6 py-3.5">CPU Utilization</th>
                    <th className="px-6 py-3.5">Availability Zone</th>
                    <th className="px-6 py-3.5">Launch Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {filtered.map((inst) => (
                    <tr key={inst.instanceId} className="hover:bg-[#F8FAFC] transition-colors">
                      <td className="px-6 py-4 font-mono font-bold text-[#0284C7]">{inst.instanceId}</td>
                      <td className="px-6 py-4 font-bold text-[#0F172A]">{inst.name}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${getStatusBadgeClass(inst.status)}`}>
                          {inst.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-[#0F172A]">{inst.instanceType}</td>
                      <td className="px-6 py-4 font-bold text-[#0F172A]">{inst.cpu}</td>
                      <td className="px-6 py-4 text-[#64748B]">{inst.az}</td>
                      <td className="px-6 py-4 text-[#64748B]">{inst.launchTime}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* 2. VPC Table */}
            {activeTab === 'vpc' && (
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F8FAFC] text-[#475569] uppercase tracking-wider font-semibold border-b border-[#E2E8F0]">
                  <tr>
                    <th className="px-6 py-3.5">VPC ID</th>
                    <th className="px-6 py-3.5">Name</th>
                    <th className="px-6 py-3.5">CIDR Block</th>
                    <th className="px-6 py-3.5">Subnets Count</th>
                    <th className="px-6 py-3.5">State</th>
                    <th className="px-6 py-3.5">Default VPC</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {filtered.map((v) => (
                    <tr key={v.vpcId} className="hover:bg-[#F8FAFC] transition-colors">
                      <td className="px-6 py-4 font-mono font-bold text-[#0284C7]">{v.vpcId}</td>
                      <td className="px-6 py-4 font-bold text-[#0F172A]">{v.name}</td>
                      <td className="px-6 py-4 font-mono text-[#0F172A]">{v.cidrBlock}</td>
                      <td className="px-6 py-4 font-bold text-[#0284C7]">{v.subnetsCount} Subnets</td>
                      <td className="px-6 py-4">
                        <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-semibold">
                          {v.state}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-[#64748B]">{v.defaultVpc ? 'Yes' : 'No'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* 3. Security Groups Table */}
            {activeTab === 'securityGroups' && (
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F8FAFC] text-[#475569] uppercase tracking-wider font-semibold border-b border-[#E2E8F0]">
                  <tr>
                    <th className="px-6 py-3.5">Group ID</th>
                    <th className="px-6 py-3.5">Group Name</th>
                    <th className="px-6 py-3.5">VPC ID</th>
                    <th className="px-6 py-3.5">Inbound Rules</th>
                    <th className="px-6 py-3.5">Outbound Rules</th>
                    <th className="px-6 py-3.5">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {filtered.map((sg) => (
                    <tr key={sg.groupId} className="hover:bg-[#F8FAFC] transition-colors">
                      <td className="px-6 py-4 font-mono font-bold text-[#0284C7]">{sg.groupId}</td>
                      <td className="px-6 py-4 font-bold text-[#0F172A]">{sg.name}</td>
                      <td className="px-6 py-4 font-mono text-[#64748B]">{sg.vpcId}</td>
                      <td className="px-6 py-4 font-bold text-[#0284C7]">{sg.inboundRules} Ingress</td>
                      <td className="px-6 py-4 font-bold text-[#0F172A]">{sg.outboundRules} Egress</td>
                      <td className="px-6 py-4 text-[#64748B]">{sg.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* 4. Load Balancers Table */}
            {activeTab === 'loadBalancers' && (
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F8FAFC] text-[#475569] uppercase tracking-wider font-semibold border-b border-[#E2E8F0]">
                  <tr>
                    <th className="px-6 py-3.5">ALB Name</th>
                    <th className="px-6 py-3.5">DNS Hostname</th>
                    <th className="px-6 py-3.5">Type</th>
                    <th className="px-6 py-3.5">State</th>
                    <th className="px-6 py-3.5">Target Groups</th>
                    <th className="px-6 py-3.5">Scheme</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {filtered.map((alb) => (
                    <tr key={alb.albName} className="hover:bg-[#F8FAFC] transition-colors">
                      <td className="px-6 py-4 font-bold text-[#0F172A]">{alb.albName}</td>
                      <td className="px-6 py-4 font-mono text-[#64748B] truncate max-w-xs">{alb.dnsName}</td>
                      <td className="px-6 py-4 font-semibold text-[#0F172A] uppercase">{alb.type}</td>
                      <td className="px-6 py-4">
                        <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-[11px] font-semibold">
                          {alb.state}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-bold text-[#0284C7]">{alb.targetGroupsCount} Groups</td>
                      <td className="px-6 py-4 text-[#64748B]">{alb.scheme}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* 5. CloudWatch Alarms Table */}
            {activeTab === 'cloudWatch' && (
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F8FAFC] text-[#475569] uppercase tracking-wider font-semibold border-b border-[#E2E8F0]">
                  <tr>
                    <th className="px-6 py-3.5">Alarm Name</th>
                    <th className="px-6 py-3.5">Target Metric</th>
                    <th className="px-6 py-3.5">Threshold</th>
                    <th className="px-6 py-3.5">State</th>
                    <th className="px-6 py-3.5">Last Updated</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {filtered.map((cw) => (
                    <tr key={cw.alarmName} className="hover:bg-[#F8FAFC] transition-colors">
                      <td className="px-6 py-4 font-bold text-[#0F172A]">{cw.alarmName}</td>
                      <td className="px-6 py-4 font-mono text-[#0284C7]">{cw.metric}</td>
                      <td className="px-6 py-4 font-bold text-[#0F172A]">{cw.threshold}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${getStatusBadgeClass(cw.state)}`}>
                          {cw.state}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-[#64748B]">{cw.updatedAt}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
