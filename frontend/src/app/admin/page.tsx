'use client';

import React, { useState, useEffect } from 'react';
import {
  AdminOverviewResponse,
  AdminDataSourceItem,
  IngestionRunRead,
  AdminIngestionRunDetail,
  DataQualityReviewItemRead,
  DataConflictRead,
  AdminFreshnessResponse,
  AdminQualityResponse,
  UserRead,
} from '@/types';
import { api, authStorage } from '@/lib/api';

type AdminTab = 'overview' | 'sources' | 'runs' | 'reviews' | 'conflicts' | 'freshness_quality';

export default function AdminDashboardPage() {
  const [currentUser, setCurrentUser] = useState<UserRead | null>(null);
  const [authChecked, setAuthChecked] = useState<boolean>(false);
  const [loginEmail, setLoginEmail] = useState<string>('admin@carafford.in');
  const [loginPassword, setLoginPassword] = useState<string>('CarAffordAdmin#2026');
  const [loginLoading, setLoginLoading] = useState<boolean>(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<AdminTab>('overview');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Tab Data States
  const [overviewData, setOverviewData] = useState<AdminOverviewResponse | null>(null);
  const [sources, setSources] = useState<AdminDataSourceItem[]>([]);
  const [runs, setRuns] = useState<IngestionRunRead[]>([]);
  const [selectedRunDetail, setSelectedRunDetail] = useState<AdminIngestionRunDetail | null>(null);
  const [loadingRunDetail, setLoadingRunDetail] = useState<boolean>(false);
  const [reviews, setReviews] = useState<DataQualityReviewItemRead[]>([]);
  const [conflicts, setConflicts] = useState<DataConflictRead[]>([]);
  const [freshnessData, setFreshnessData] = useState<AdminFreshnessResponse | null>(null);
  const [qualityData, setQualityData] = useState<AdminQualityResponse | null>(null);

  // Review & Conflict Action States
  const [actionReviewModal, setActionReviewModal] = useState<{ item: DataQualityReviewItemRead; action: 'APPROVE' | 'REJECT' } | null>(null);
  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [conflictModal, setConflictModal] = useState<DataConflictRead | null>(null);
  const [acceptedSourceId, setAcceptedSourceId] = useState<number | null>(null);
  const [conflictNotes, setConflictNotes] = useState<string>('');

  // Initial Auth Check
  useEffect(() => {
    checkAuthentication();
  }, []);

  const checkAuthentication = async () => {
    try {
      setLoginLoading(true);
      const user = await api.getMe();
      if (user && (user.role === 'ADMIN' || user.is_superuser)) {
        setCurrentUser(user);
      } else {
        setCurrentUser(null);
      }
    } catch {
      setCurrentUser(null);
    } finally {
      setLoginLoading(false);
      setAuthChecked(true);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError(null);
    try {
      const res = await api.login({ email: loginEmail, password: loginPassword });
      if (res.user && (res.user.role === 'ADMIN' || res.user.is_superuser)) {
        setCurrentUser(res.user);
      } else {
        setLoginError('Account does not have administrative privileges.');
        api.logout();
      }
    } catch (err: any) {
      setLoginError(err.message || 'Invalid administrator email or password.');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    api.logout();
    setCurrentUser(null);
    setOverviewData(null);
  };

  // Fetch when tab changes or when logged in
  useEffect(() => {
    if (!currentUser) return;
    setError(null);
    setActionMessage(null);
    if (activeTab === 'overview') loadOverview();
    else if (activeTab === 'sources') loadSources();
    else if (activeTab === 'runs') loadRuns();
    else if (activeTab === 'reviews') loadReviews();
    else if (activeTab === 'conflicts') loadConflicts();
    else if (activeTab === 'freshness_quality') loadFreshnessAndQuality();
  }, [activeTab, currentUser]);

  const loadOverview = async () => {
    try {
      setLoading(true);
      const data = await api.getAdminOverview();
      setOverviewData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load admin overview data');
    } finally {
      setLoading(false);
    }
  };

  const loadSources = async () => {
    try {
      setLoading(true);
      const data = await api.getAdminDataSources();
      setSources(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load data sources');
    } finally {
      setLoading(false);
    }
  };

  const loadRuns = async () => {
    try {
      setLoading(true);
      const data = await api.getAdminIngestionRuns({ limit: 50 });
      setRuns(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load ingestion runs');
    } finally {
      setLoading(false);
    }
  };

  const loadRunDetail = async (runId: number) => {
    try {
      setLoadingRunDetail(true);
      const detail = await api.getAdminIngestionRunDetail(runId);
      setSelectedRunDetail(detail);
    } catch (err: any) {
      setError(err.message || `Failed to load audit detail for Run #${runId}`);
    } finally {
      setLoadingRunDetail(false);
    }
  };

  const loadReviews = async () => {
    try {
      setLoading(true);
      const data = await api.getAdminReviewQueue();
      setReviews(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load review items');
    } finally {
      setLoading(false);
    }
  };

  const loadConflicts = async () => {
    try {
      setLoading(true);
      const data = await api.getAdminConflicts();
      setConflicts(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load conflicts');
    } finally {
      setLoading(false);
    }
  };

  const loadFreshnessAndQuality = async () => {
    try {
      setLoading(true);
      const [fresh, qual] = await Promise.all([
        api.getAdminFreshness(),
        api.getAdminQuality(),
      ]);
      setFreshnessData(fresh);
      setQualityData(qual);
    } catch (err: any) {
      setError(err.message || 'Failed to load freshness and quality reports');
    } finally {
      setLoading(false);
    }
  };

  // Actions
  const handleToggleSource = async (sourceId: number) => {
    try {
      const updated = await api.toggleDataSource(sourceId);
      setSources((prev) => prev.map((s) => (s.id === sourceId ? updated : s)));
      setActionMessage({
        type: 'success',
        text: `Data Source "${updated.name}" is now ${updated.is_active ? 'ACTIVE' : 'INACTIVE'}`,
      });
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message || 'Failed to toggle source status' });
    }
  };

  const handleActionReview = async () => {
    if (!actionReviewModal) return;
    try {
      const result = await api.actionReviewItem(actionReviewModal.item.id, actionReviewModal.action, reviewNotes);
      setReviews((prev) => prev.filter((r) => r.id !== result.id));
      setActionMessage({
        type: 'success',
        text: `Review Item #${result.id} marked as ${result.status}`,
      });
      setActionReviewModal(null);
      setReviewNotes('');
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message || 'Failed to submit review action' });
    }
  };

  const handleResolveConflict = async () => {
    if (!conflictModal || !acceptedSourceId) return;
    try {
      const resolved = await api.resolveAdminConflict(conflictModal.id, acceptedSourceId, conflictNotes);
      setConflicts((prev) => prev.map((c) => (c.id === resolved.id ? resolved : c)));
      setActionMessage({
        type: 'success',
        text: `Conflict #${resolved.id} successfully resolved with Source ID #${acceptedSourceId}`,
      });
      setConflictModal(null);
      setAcceptedSourceId(null);
      setConflictNotes('');
    } catch (err: any) {
      setActionMessage({ type: 'error', text: err.message || 'Failed to resolve conflict' });
    }
  };

  const getBadgeClass = (status: string) => {
    switch (status?.toUpperCase()) {
      case 'CURRENT':
      case 'SUCCESS':
      case 'COMPLETED':
      case 'APPROVED':
      case 'EXCELLENT':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300';
      case 'STALE':
      case 'PENDING':
      case 'GOOD':
      case 'IN_PROGRESS':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'EXPIRED':
      case 'FAILED':
      case 'REJECTED':
      case 'POOR':
      case 'UNRESOLVED':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      case 'FIXTURE_ONLY':
        return 'bg-purple-100 text-purple-800 border-purple-300';
      case 'MANUAL_REVIEW':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-300';
    }
  };

  // If Auth check not finished, show loader
  if (!authChecked) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  // If not logged in as Admin, show Login Gate
  if (!currentUser) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl space-y-6">
          <div className="text-center space-y-2">
            <div className="w-14 h-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 mx-auto flex items-center justify-center">
              <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-white">Administrator Access</h2>
            <p className="text-xs text-slate-400">Sign in with administrative credentials to manage data sources, governance queues, and audit logs.</p>
          </div>

          {loginError && (
            <div className="p-3 bg-rose-950/60 border border-rose-800 text-rose-300 rounded-xl text-xs">
              {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Admin Email</label>
              <input
                type="email"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                required
                className="w-full px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Password</label>
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                required
                className="w-full px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-indigo-500"
              />
            </div>

            <button
              type="submit"
              disabled={loginLoading}
              className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-sm font-bold shadow-lg shadow-indigo-600/30 transition-all"
            >
              {loginLoading ? 'Authenticating...' : 'Sign In as Administrator'}
            </button>
          </form>

          <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-xl text-[11px] text-slate-400 space-y-1">
            <span className="font-semibold text-slate-300 block">Default Seed Credentials:</span>
            <div>Email: <code className="text-indigo-400">admin@carafford.in</code></div>
            <div>Password: <code className="text-indigo-400">CarAffordAdmin#2026</code></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto space-y-6">
        
        {/* Header & Notice Banner */}
        <div className="bg-slate-800/90 border border-slate-700 rounded-2xl p-6 shadow-xl backdrop-blur-md">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center justify-center p-2 bg-indigo-600/20 text-indigo-400 rounded-lg border border-indigo-500/30">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </span>
                <h1 className="text-2xl font-bold tracking-tight text-white">Data Quality & Governance Portal</h1>
              </div>
              <p className="text-slate-400 text-sm mt-1">
                Domain 17: Production Hardening, RBAC Authorization, Ingestion Oversight, and Quality Scorecards.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right text-xs">
                <span className="font-semibold text-white block">{currentUser.full_name || currentUser.email}</span>
                <span className="text-indigo-400 font-mono text-[10px]">{currentUser.role}</span>
              </div>
              <button
                onClick={handleLogout}
                className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 hover:text-white rounded-lg text-xs font-semibold"
              >
                Logout
              </button>
            </div>
          </div>
        </div>

        {/* Action / Error Alerts */}
        {actionMessage && (
          <div className={`p-4 rounded-xl text-sm flex items-center justify-between border ${
            actionMessage.type === 'success'
              ? 'bg-emerald-950/60 text-emerald-300 border-emerald-700/50'
              : 'bg-rose-950/60 text-rose-300 border-rose-700/50'
          }`}>
            <span>{actionMessage.text}</span>
            <button onClick={() => setActionMessage(null)} className="text-xs font-bold hover:underline ml-4">Dismiss</button>
          </div>
        )}

        {error && (
          <div className="p-4 bg-rose-950/60 text-rose-300 border border-rose-700/50 rounded-xl text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-xs font-bold hover:underline ml-4">Dismiss</button>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-3">
          {[
            { id: 'overview', label: 'Overview & Health', icon: '📊' },
            { id: 'sources', label: 'Data Sources', icon: '🌐' },
            { id: 'runs', label: 'Ingestion Runs', icon: '⚡' },
            { id: 'reviews', label: 'Review Queue', icon: '📝' },
            { id: 'conflicts', label: 'Conflicts', icon: '⚖️' },
            { id: 'freshness_quality', label: 'Freshness & Quality', icon: '🎯' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as AdminTab)}
              className={`px-4 py-2.5 rounded-xl font-medium text-sm transition-all flex items-center gap-2 ${
                activeTab === tab.id
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                  : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700/80 hover:text-white'
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.id === 'reviews' && overviewData && overviewData.pending_review_items > 0 && (
                <span className="ml-1.5 px-2 py-0.5 text-xs bg-amber-500 text-slate-950 font-bold rounded-full">
                  {overviewData.pending_review_items}
                </span>
              )}
              {tab.id === 'conflicts' && overviewData && overviewData.unresolved_conflicts > 0 && (
                <span className="ml-1.5 px-2 py-0.5 text-xs bg-rose-500 text-white font-bold rounded-full">
                  {overviewData.unresolved_conflicts}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Loading Spinner */}
        {loading && (
          <div className="py-20 flex flex-col items-center justify-center space-y-4">
            <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-slate-400 text-sm">Querying data governance engine...</p>
          </div>
        )}

        {/* Tab 1: Overview */}
        {!loading && activeTab === 'overview' && overviewData && (
          <div className="space-y-6">
            {/* KPI Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-5 shadow-lg">
                <div className="flex justify-between items-start">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Overall Quality</span>
                  <span className={`text-xs px-2.5 py-0.5 rounded-full border font-bold ${getBadgeClass(overviewData.quality_rating)}`}>
                    {overviewData.quality_rating}
                  </span>
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-white">{Number(overviewData.overall_quality_score).toFixed(1)}</span>
                  <span className="text-slate-400 text-sm">/ 100</span>
                </div>
                <div className="mt-3 w-full bg-slate-700 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-indigo-500 to-emerald-400 h-full rounded-full"
                    style={{ width: `${Math.min(100, Math.max(0, Number(overviewData.overall_quality_score)))}%` }}
                  ></div>
                </div>
              </div>

              <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-5 shadow-lg">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Data Sources</span>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-white">{overviewData.active_sources}</span>
                  <span className="text-slate-400 text-sm">active ({overviewData.total_data_sources} total)</span>
                </div>
                <div className="mt-3 flex gap-2 text-xs text-slate-400">
                  <span className="text-purple-300">📁 {overviewData.fixture_only_sources} Fixture</span>
                  <span className="text-blue-300">👤 {overviewData.manual_review_sources} Manual</span>
                </div>
              </div>

              <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-5 shadow-lg">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Review & Conflicts</span>
                <div className="mt-3 flex items-baseline gap-3">
                  <div>
                    <span className="text-2xl font-bold text-amber-400">{overviewData.pending_review_items}</span>
                    <span className="text-xs text-slate-400 block">Pending Review</span>
                  </div>
                  <div className="border-l border-slate-700 pl-3">
                    <span className="text-2xl font-bold text-rose-400">{overviewData.unresolved_conflicts}</span>
                    <span className="text-xs text-slate-400 block">Open Conflicts</span>
                  </div>
                </div>
                <div className="mt-3 text-xs text-slate-400">Requires administrator verification</div>
              </div>

              <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-5 shadow-lg">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Ingestion Runs</span>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-white">{overviewData.total_ingestion_runs}</span>
                  <span className="text-slate-400 text-sm">executed</span>
                </div>
                <div className="mt-3 flex gap-2 text-xs text-slate-400">
                  <span className={overviewData.failed_ingestion_runs > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                    ❌ {overviewData.failed_ingestion_runs} Failed
                  </span>
                  <span className="text-amber-400">⏱️ {overviewData.stale_datasets} Stale</span>
                </div>
              </div>
            </div>

            {/* Datasets Freshness Quick Summary */}
            <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-6 shadow-xl">
              <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                <span>🕒</span>
                <span>Dataset Freshness SLA Status</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-700 text-left text-sm">
                  <thead>
                    <tr className="text-xs text-slate-400 uppercase">
                      <th className="py-3 px-4">Dataset Name</th>
                      <th className="py-3 px-4">Freshness SLA</th>
                      <th className="py-3 px-4">Last Synced</th>
                      <th className="py-3 px-4">Age (Days)</th>
                      <th className="py-3 px-4">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {overviewData.datasets_freshness_summary.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-750/50">
                        <td className="py-3 px-4 font-mono font-medium text-slate-200">{item.dataset_name}</td>
                        <td className="py-3 px-4 text-slate-400">{item.sla_days} days</td>
                        <td className="py-3 px-4 text-slate-400">
                          {item.last_synced_at ? new Date(item.last_synced_at).toLocaleString() : 'Never'}
                        </td>
                        <td className="py-3 px-4 text-slate-300">{item.age_days !== null && item.age_days !== undefined ? `${item.age_days}d` : '—'}</td>
                        <td className="py-3 px-4">
                          <span className={`text-xs px-2.5 py-1 rounded-full border font-bold ${getBadgeClass(item.status)}`}>
                            {item.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Data Sources */}
        {!loading && activeTab === 'sources' && (
          <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-white">Registered Ingestion Sources</h3>
                <p className="text-slate-400 text-xs mt-1">Manage external sources, toggle active ingestion flags, and monitor trust tiers.</p>
              </div>
              <span className="text-xs text-slate-400 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-700">
                {sources.length} Data Sources Configured
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-700 text-left text-sm">
                <thead>
                  <tr className="text-xs text-slate-400 uppercase">
                    <th className="py-3 px-4">Source Name</th>
                    <th className="py-3 px-4">Access Mode</th>
                    <th className="py-3 px-4">Trust Level</th>
                    <th className="py-3 px-4">SLA (Days)</th>
                    <th className="py-3 px-4">Freshness</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {sources.map((src) => (
                    <tr key={src.id} className="hover:bg-slate-750/50">
                      <td className="py-3 px-4">
                        <div className="font-medium text-white">{src.name}</div>
                        <div className="text-xs font-mono text-slate-400">{src.slug} {src.organization && `• ${src.organization}`}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-xs px-2.5 py-1 rounded-full border font-bold ${getBadgeClass(src.access_mode)}`}>
                          {src.access_mode}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-sm font-bold text-indigo-400">{src.trust_level}/100</span>
                      </td>
                      <td className="py-3 px-4 text-slate-300">{src.freshness_sla_days}d</td>
                      <td className="py-3 px-4">
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${getBadgeClass(src.freshness_status)}`}>
                          {src.freshness_status}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-xs px-2.5 py-1 rounded-full font-bold ${
                          src.is_active ? 'bg-emerald-900/60 text-emerald-300' : 'bg-slate-700 text-slate-400'
                        }`}>
                          {src.is_active ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => handleToggleSource(src.id)}
                          className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all ${
                            src.is_active
                              ? 'bg-rose-900/40 text-rose-300 border border-rose-700 hover:bg-rose-800/60'
                              : 'bg-emerald-900/40 text-emerald-300 border border-emerald-700 hover:bg-emerald-800/60'
                          }`}
                        >
                          {src.is_active ? 'Disable' : 'Enable'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 3: Ingestion Runs */}
        {!loading && activeTab === 'runs' && (
          <div className="space-y-6">
            <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-6 shadow-xl">
              <h3 className="text-lg font-bold text-white mb-4">Ingestion Run Audit History</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-700 text-left text-sm">
                  <thead>
                    <tr className="text-xs text-slate-400 uppercase">
                      <th className="py-3 px-4">Run ID</th>
                      <th className="py-3 px-4">Dataset</th>
                      <th className="py-3 px-4">Started</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Records (Seen / Mod / Rej)</th>
                      <th className="py-3 px-4">Errors</th>
                      <th className="py-3 px-4 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {runs.map((run) => (
                      <tr key={run.id} className="hover:bg-slate-750/50">
                        <td className="py-3 px-4 font-mono font-bold text-indigo-400">#{run.id}</td>
                        <td className="py-3 px-4 font-medium text-slate-200">{run.dataset_name}</td>
                        <td className="py-3 px-4 text-xs text-slate-400">{new Date(run.started_at).toLocaleString()}</td>
                        <td className="py-3 px-4">
                          <span className={`text-xs px-2.5 py-1 rounded-full border font-bold ${getBadgeClass(run.status)}`}>
                            {run.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-300">
                          {run.records_seen} seen / <span className="text-emerald-400">+{run.records_created}</span> / <span className="text-rose-400">✕{run.records_rejected}</span>
                        </td>
                        <td className="py-3 px-4 text-xs">
                          {run.error_count > 0 || run.validation_error_count > 0 ? (
                            <span className="text-rose-400 font-semibold">{run.error_count + run.validation_error_count} errs</span>
                          ) : (
                            <span className="text-emerald-400">0</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => loadRunDetail(run.id)}
                            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600/30 text-indigo-300 border border-indigo-500/50 hover:bg-indigo-600/50 font-medium"
                          >
                            Audit Details
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Run Detail View */}
            {selectedRunDetail && (
              <div className="bg-slate-800/90 border border-indigo-500/60 rounded-2xl p-6 shadow-2xl space-y-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-lg font-bold text-white">Audit Trail: Ingestion Run #{selectedRunDetail.run.id}</h4>
                    <p className="text-xs text-indigo-300 mt-0.5">Dataset: {selectedRunDetail.run.dataset_name}</p>
                  </div>
                  <button
                    onClick={() => setSelectedRunDetail(null)}
                    className="text-xs px-3 py-1 rounded bg-slate-700 text-slate-300 hover:text-white"
                  >
                    Close
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="p-3 bg-slate-900/70 rounded-xl border border-slate-700">
                    <span className="text-slate-400 block">Raw Records Ingested</span>
                    <span className="text-lg font-bold text-white">{selectedRunDetail.raw_records_count}</span>
                  </div>
                  <div className="p-3 bg-slate-900/70 rounded-xl border border-slate-700">
                    <span className="text-slate-400 block">Validation Failures</span>
                    <span className="text-lg font-bold text-rose-400">{selectedRunDetail.run.validation_error_count}</span>
                  </div>
                  <div className="p-3 bg-slate-900/70 rounded-xl border border-slate-700">
                    <span className="text-slate-400 block">Conflicts Triggered</span>
                    <span className="text-lg font-bold text-amber-400">{selectedRunDetail.conflicts_detected.length}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Review Queue */}
        {!loading && activeTab === 'reviews' && (
          <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-lg font-bold text-white">Manual Verification Queue</h3>
                <p className="text-slate-400 text-xs mt-1">Review flagged updates, price revisions, and tax overrides requiring human sign-off.</p>
              </div>
              <span className="text-xs text-amber-300 bg-amber-950/60 px-3 py-1.5 rounded-lg border border-amber-800/50">
                {reviews.length} Items Pending Review
              </span>
            </div>

            {reviews.length === 0 ? (
              <div className="py-12 text-center text-slate-400 text-sm">
                🎉 No items currently pending in the manual review queue.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-700 text-left text-sm">
                  <thead>
                    <tr className="text-xs text-slate-400 uppercase">
                      <th className="py-3 px-4">Item ID</th>
                      <th className="py-3 px-4">Entity & Identifier</th>
                      <th className="py-3 px-4">Field</th>
                      <th className="py-3 px-4">Current Value</th>
                      <th className="py-3 px-4">Proposed Value</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {reviews.map((rev) => (
                      <tr key={rev.id} className="hover:bg-slate-750/50">
                        <td className="py-3 px-4 font-mono font-bold text-indigo-400">#{rev.id}</td>
                        <td className="py-3 px-4">
                          <span className="font-semibold text-slate-200 block">{rev.entity_type}</span>
                          <span className="text-xs font-mono text-slate-400">{rev.entity_identifier}</span>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-300 text-xs">{rev.field_name}</td>
                        <td className="py-3 px-4 text-xs text-slate-400">{rev.current_value !== null ? String(rev.current_value) : '—'}</td>
                        <td className="py-3 px-4 text-xs font-bold text-emerald-400">{String(rev.proposed_value)}</td>
                        <td className="py-3 px-4">
                          <span className={`text-xs px-2.5 py-0.5 rounded-full border font-bold ${getBadgeClass(rev.status)}`}>
                            {rev.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => {
                                setActionReviewModal({ item: rev, action: 'APPROVE' });
                                setReviewNotes('');
                              }}
                              className="text-xs px-3 py-1 bg-emerald-900/60 text-emerald-300 border border-emerald-700 rounded-lg hover:bg-emerald-800"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => {
                                setActionReviewModal({ item: rev, action: 'REJECT' });
                                setReviewNotes('');
                              }}
                              className="text-xs px-3 py-1 bg-rose-900/60 text-rose-300 border border-rose-700 rounded-lg hover:bg-rose-800"
                            >
                              Reject
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 5: Conflicts */}
        {!loading && activeTab === 'conflicts' && (
          <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-6 shadow-xl space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-lg font-bold text-white">Multi-Source Discrepancies & Conflict Resolution</h3>
                <p className="text-slate-400 text-xs mt-1">Resolve field discrepancies when two external data sources provide conflicting values.</p>
              </div>
              <span className="text-xs text-rose-300 bg-rose-950/60 px-3 py-1.5 rounded-lg border border-rose-800/50">
                {conflicts.filter((c) => c.status === 'UNRESOLVED').length} Unresolved
              </span>
            </div>

            {conflicts.length === 0 ? (
              <div className="py-12 text-center text-slate-400 text-sm">
                🛡️ No conflicting records detected across any registered datasets.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-700 text-left text-sm">
                  <thead>
                    <tr className="text-xs text-slate-400 uppercase">
                      <th className="py-3 px-4">Conflict ID</th>
                      <th className="py-3 px-4">Dataset / Entity</th>
                      <th className="py-3 px-4">Field</th>
                      <th className="py-3 px-4">Source A (ID #{conflicts[0]?.source_a_id})</th>
                      <th className="py-3 px-4">Source B (ID #{conflicts[0]?.source_b_id})</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Resolution</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/50">
                    {conflicts.map((conf) => (
                      <tr key={conf.id} className="hover:bg-slate-750/50">
                        <td className="py-3 px-4 font-mono font-bold text-indigo-400">#{conf.id}</td>
                        <td className="py-3 px-4">
                          <span className="font-semibold text-slate-200 block">{conf.dataset_name}</span>
                          <span className="text-xs font-mono text-slate-400">{conf.entity_identifier}</span>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-300 text-xs">{conf.field_name}</td>
                        <td className="py-3 px-4 text-xs font-mono bg-slate-900/50 text-indigo-300 p-2 rounded">
                          {String(conf.source_a_value)}
                        </td>
                        <td className="py-3 px-4 text-xs font-mono bg-slate-900/50 text-amber-300 p-2 rounded">
                          {String(conf.source_b_value)}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`text-xs px-2.5 py-0.5 rounded-full border font-bold ${getBadgeClass(conf.status)}`}>
                            {conf.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right">
                          {conf.status === 'UNRESOLVED' ? (
                            <button
                              onClick={() => {
                                setConflictModal(conf);
                                setAcceptedSourceId(conf.source_a_id);
                                setConflictNotes('');
                              }}
                              className="text-xs px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 font-medium"
                            >
                              Resolve
                            </button>
                          ) : (
                            <span className="text-xs text-slate-400 italic">Resolved</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Tab 6: Freshness & Quality Scorecard */}
        {!loading && activeTab === 'freshness_quality' && (
          <div className="space-y-6">
            {/* 4 Pillars Quality Scorecard */}
            {qualityData && (
              <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-6 shadow-xl space-y-5">
                <div className="flex flex-col sm:flex-row justify-between sm:items-center gap-4">
                  <div>
                    <h3 className="text-lg font-bold text-white">4-Pillar Composite Data Quality Scorecard</h3>
                    <p className="text-slate-400 text-xs mt-0.5">{qualityData.score_change_explanation}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-2xl font-black text-emerald-400">{Number(qualityData.overall_score).toFixed(1)}/100</span>
                    <span className={`text-xs px-2.5 py-1 rounded-full border font-bold ${getBadgeClass(qualityData.rating)}`}>
                      {qualityData.rating}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  {qualityData.pillars.map((pillar) => (
                    <div key={pillar.pillar_key} className="bg-slate-900/60 border border-slate-700 p-4 rounded-xl space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-semibold text-slate-300">{pillar.pillar_name}</span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold ${getBadgeClass(pillar.status)}`}>
                          {pillar.status}
                        </span>
                      </div>
                      <div className="text-2xl font-extrabold text-white">
                        {Number(pillar.score).toFixed(1)} <span className="text-xs font-normal text-slate-400">({Number(pillar.weight_pct)}% weight)</span>
                      </div>
                      <p className="text-[11px] text-slate-400">{pillar.description}</p>
                    </div>
                  ))}
                </div>

                {qualityData.recommendations.length > 0 && (
                  <div className="p-4 bg-indigo-950/40 border border-indigo-800/50 rounded-xl space-y-2">
                    <span className="text-xs font-bold text-indigo-300 uppercase tracking-wider">Quality Improvement Recommendations</span>
                    <ul className="text-xs text-indigo-200 space-y-1 list-disc list-inside">
                      {qualityData.recommendations.map((rec, i) => (
                        <li key={i}>{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Functional Domain Freshness */}
            {freshnessData && (
              <div className="bg-slate-800/80 border border-slate-700/70 rounded-2xl p-6 shadow-xl space-y-5">
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="text-lg font-bold text-white">Functional Domain Freshness</h3>
                    <p className="text-slate-400 text-xs mt-0.5">Automated SLA health monitoring per data category.</p>
                  </div>
                  <span className="text-xs font-bold text-emerald-400 bg-emerald-950/60 px-3 py-1.5 rounded-lg border border-emerald-800/50">
                    {Number(freshnessData.overall_freshness_pct).toFixed(1)}% In SLA
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {freshnessData.domains.map((dom) => (
                    <div key={dom.domain_key} className="bg-slate-900/60 border border-slate-700 p-5 rounded-xl space-y-3">
                      <div className="flex justify-between items-center">
                        <h4 className="font-bold text-slate-200 text-sm">{dom.domain_name}</h4>
                        <div className="flex gap-2 text-xs">
                          <span className="text-emerald-400 font-semibold">{dom.current_count} current</span>
                          {dom.stale_count > 0 && <span className="text-amber-400 font-semibold">{dom.stale_count} stale</span>}
                          {dom.expired_count > 0 && <span className="text-rose-400 font-semibold">{dom.expired_count} expired</span>}
                        </div>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t border-slate-800">
                        {dom.datasets.map((ds, i) => (
                          <div key={i} className="flex justify-between items-center text-xs py-1">
                            <span className="font-mono text-slate-300">{ds.dataset_name}</span>
                            <div className="flex items-center gap-2">
                              <span className="text-slate-400">{ds.age_days !== null && ds.age_days !== undefined ? `${ds.age_days}d old` : '—'}</span>
                              <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold ${getBadgeClass(ds.status)}`}>
                                {ds.status}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Review Action Modal */}
        {actionReviewModal && (
          <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
              <h3 className="text-lg font-bold text-white">
                {actionReviewModal.action === 'APPROVE' ? '✅ Approve Review Item' : '❌ Reject Review Item'} #{actionReviewModal.item.id}
              </h3>
              <div className="text-xs bg-slate-900 p-3 rounded-xl border border-slate-800 space-y-1 font-mono">
                <div><span className="text-slate-400">Entity:</span> {actionReviewModal.item.entity_type} ({actionReviewModal.item.entity_identifier})</div>
                <div><span className="text-slate-400">Field:</span> {actionReviewModal.item.field_name}</div>
                <div><span className="text-slate-400">Proposed Value:</span> <span className="text-emerald-400">{String(actionReviewModal.item.proposed_value)}</span></div>
              </div>
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Reviewer Justification Notes</label>
                <textarea
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="Provide audit reason for approval/rejection..."
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-indigo-500 min-h-[80px]"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setActionReviewModal(null)}
                  className="px-4 py-2 bg-slate-700 text-slate-300 hover:text-white rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  onClick={handleActionReview}
                  className={`px-4 py-2 rounded-xl text-xs font-bold text-white ${
                    actionReviewModal.action === 'APPROVE' ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-rose-600 hover:bg-rose-500'
                  }`}
                >
                  Confirm {actionReviewModal.action}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Conflict Resolution Modal */}
        {conflictModal && (
          <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl">
              <h3 className="text-lg font-bold text-white">⚖️ Resolve Conflict #{conflictModal.id}</h3>
              <p className="text-xs text-slate-400">
                Dataset: <span className="font-mono text-slate-200">{conflictModal.dataset_name}</span> • Field: <span className="font-mono text-slate-200">{conflictModal.field_name}</span>
              </p>

              <div className="space-y-3">
                <label className="text-xs font-semibold text-slate-300 block">Select Accepted Winning Source:</label>
                <div
                  onClick={() => setAcceptedSourceId(conflictModal.source_a_id)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all ${
                    acceptedSourceId === conflictModal.source_a_id
                      ? 'bg-indigo-900/50 border-indigo-500'
                      : 'bg-slate-900 border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="text-xs font-bold text-indigo-300">Source A (ID #{conflictModal.source_a_id})</div>
                  <div className="text-sm font-mono text-white mt-1">{String(conflictModal.source_a_value)}</div>
                </div>

                <div
                  onClick={() => setAcceptedSourceId(conflictModal.source_b_id)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all ${
                    acceptedSourceId === conflictModal.source_b_id
                      ? 'bg-indigo-900/50 border-indigo-500'
                      : 'bg-slate-900 border-slate-700 hover:border-slate-600'
                  }`}
                >
                  <div className="text-xs font-bold text-amber-300">Source B (ID #{conflictModal.source_b_id})</div>
                  <div className="text-sm font-mono text-white mt-1">{String(conflictModal.source_b_value)}</div>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Resolution Justification Notes (Required)</label>
                <textarea
                  value={conflictNotes}
                  onChange={(e) => setConflictNotes(e.target.value)}
                  placeholder="Explain why this source value was chosen for resolution..."
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-indigo-500 min-h-[80px]"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setConflictModal(null)}
                  className="px-4 py-2 bg-slate-700 text-slate-300 hover:text-white rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  disabled={!conflictNotes.trim()}
                  onClick={handleResolveConflict}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold"
                >
                  Apply Resolution
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
