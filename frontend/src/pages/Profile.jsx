import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Camera,
  Trash2,
  Save,
  LogOut,
  User,
  Mail,
  Briefcase,
  CheckCircle,
  AlertCircle,
  Upload,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';

/* ─── Avatar ──────────────────────────────────────────────────────────── */
function AvatarSection({ profile, initials, uploadLoading, onUpload, onRemove }) {
  const fileRef = useRef(null);

  return (
    <div className="flex flex-col items-center space-y-3">
      {/* Avatar circle */}
      <div className="relative group">
        <div
          className="w-24 h-24 rounded-full overflow-hidden border-4 border-[#E0F2FE] shadow-lg"
        >
          {profile?.avatar_url ? (
            <img
              src={profile.avatar_url}
              alt="Profile"
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-[#0284C7] to-[#0891B2] flex items-center justify-center text-white text-3xl font-extrabold select-none">
              {initials}
            </div>
          )}
        </div>

        {/* Edit overlay */}
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploadLoading}
          className="absolute inset-0 rounded-full bg-black/40 opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center cursor-pointer"
          title="Change photo"
        >
          {uploadLoading ? (
            <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
          ) : (
            <Camera className="w-6 h-6 text-white" />
          )}
        </button>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
          e.target.value = '';
        }}
      />

      {/* Actions */}
      <div className="flex items-center space-x-2">
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploadLoading}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#F0F7FF] hover:bg-[#E0F2FE] border border-[#BAE6FD] text-xs font-semibold text-[#0284C7] transition-all disabled:opacity-50"
        >
          <Upload className="w-3.5 h-3.5" />
          <span>{profile?.avatar_url ? 'Change Photo' : 'Upload Photo'}</span>
        </button>

        {profile?.avatar_url && (
          <button
            onClick={onRemove}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-rose-50 hover:bg-rose-100 border border-rose-200 text-xs font-semibold text-rose-600 transition-all"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Remove</span>
          </button>
        )}
      </div>

      <p className="text-[11px] text-[#94A3B8] text-center">
        PNG, JPG, WEBP accepted. Max 5 MB.
      </p>
    </div>
  );
}

/* ─── Toast ───────────────────────────────────────────────────────────── */
function Toast({ msg, type, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 4000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  return (
    <div className={`flex items-center space-x-2.5 px-4 py-3 rounded-xl shadow-lg text-sm font-semibold
      ${type === 'success' ? 'bg-white border border-[#BAE6FD] text-[#0284C7]' : 'bg-white border border-rose-200 text-rose-600'}`}>
      {type === 'success'
        ? <CheckCircle className="w-4 h-4 text-[#0284C7] shrink-0" />
        : <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />}
      <span>{msg}</span>
      <button onClick={onDismiss} className="ml-1 opacity-50 hover:opacity-100">
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

/* ─── Main Profile Page ───────────────────────────────────────────────── */
export default function Profile() {
  const { user, logout } = useAuth();
  const { profile, initials, profileLoading, uploadLoading, updateProfile, uploadAvatar, removeAvatar } = useProfile();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState('');
  const [role, setRole] = useState('');
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  // Populate form when profile loads
  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name || '');
      setRole(profile.role || '');
    }
  }, [profile]);

  const showToast = (msg, type = 'success') => setToast({ msg, type });

  const handleSave = async (e) => {
    e.preventDefault();
    if (!displayName.trim()) {
      showToast('Display name cannot be empty.', 'error');
      return;
    }
    setSaving(true);
    const result = await updateProfile({ display_name: displayName.trim(), role: role.trim() });
    setSaving(false);
    if (result.success) {
      showToast('Profile updated successfully!');
    } else {
      showToast(result.message || 'Failed to save changes.', 'error');
    }
  };

  const handleUpload = async (file) => {
    if (file.size > 5 * 1024 * 1024) {
      showToast('File too large. Maximum size is 5 MB.', 'error');
      return;
    }
    const result = await uploadAvatar(file);
    if (result.success) {
      showToast('Profile photo updated!');
    } else {
      showToast(result.message || 'Upload failed.', 'error');
    }
  };

  const handleRemoveAvatar = async () => {
    await removeAvatar();
    showToast('Profile photo removed.');
  };

  const handleSignOut = async () => {
    await logout();
    navigate('/login');
  };

  if (profileLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-3 border-[#0284C7] border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-[#64748B] font-medium">Loading your profile…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8 pb-12">
      {/* ── Page Header ───────────────────────────────── */}
      <div className="flex items-center justify-between pb-6 border-b border-[#E2E8F0]">
        <div>
          <h1 className="text-3xl font-extrabold text-[#0F172A] tracking-tight">My Profile</h1>
          <p className="text-sm text-[#64748B] mt-1">Manage your CloudOps account profile and identity.</p>
        </div>
      </div>

      {/* ── Avatar ───────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-xs p-6 sm:p-8 space-y-6">
        <h2 className="text-base font-bold text-[#0F172A] pb-4 border-b border-[#E2E8F0]">Profile Photo</h2>
        <AvatarSection
          profile={profile}
          initials={initials}
          uploadLoading={uploadLoading}
          onUpload={handleUpload}
          onRemove={handleRemoveAvatar}
        />
      </div>

      {/* ── Profile Info Form ─────────────────────────── */}
      <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-xs p-6 sm:p-8">
        <h2 className="text-base font-bold text-[#0F172A] pb-4 mb-6 border-b border-[#E2E8F0]">Profile Information</h2>

        <form onSubmit={handleSave} className="space-y-5">
          {/* Display Name */}
          <div className="space-y-1.5">
            <label className="flex items-center space-x-1.5 text-xs font-bold text-[#475569] uppercase tracking-wider">
              <User className="w-3.5 h-3.5 text-[#0284C7]" />
              <span>Display Name</span>
            </label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your full name"
              className="w-full px-4 py-2.5 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] text-sm text-[#0F172A] font-medium focus:outline-none focus:border-[#0284C7] focus:bg-white focus:ring-2 focus:ring-[#0284C7]/10 transition-all placeholder-[#94A3B8]"
            />
          </div>

          {/* Email (read-only) */}
          <div className="space-y-1.5">
            <label className="flex items-center space-x-1.5 text-xs font-bold text-[#475569] uppercase tracking-wider">
              <Mail className="w-3.5 h-3.5 text-[#0284C7]" />
              <span>Email Address</span>
            </label>
            <input
              type="email"
              value={profile?.email || user?.email || ''}
              disabled
              className="w-full px-4 py-2.5 rounded-xl border border-[#E2E8F0] bg-[#F1F5F9] text-sm text-[#64748B] font-medium cursor-not-allowed"
            />
            <p className="text-[11px] text-[#94A3B8]">Email is managed through your account authentication settings.</p>
          </div>

          {/* Role */}
          <div className="space-y-1.5">
            <label className="flex items-center space-x-1.5 text-xs font-bold text-[#475569] uppercase tracking-wider">
              <Briefcase className="w-3.5 h-3.5 text-[#0284C7]" />
              <span>Job Title / Role</span>
            </label>
            <input
              type="text"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g. Cloud Engineer, DevOps Specialist"
              className="w-full px-4 py-2.5 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] text-sm text-[#0F172A] font-medium focus:outline-none focus:border-[#0284C7] focus:bg-white focus:ring-2 focus:ring-[#0284C7]/10 transition-all placeholder-[#94A3B8]"
            />
          </div>

          {/* Save button */}
          <div className="pt-2">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center space-x-2 px-6 py-2.5 rounded-xl bg-[#0284C7] hover:bg-[#0369A1] text-white text-sm font-semibold shadow-sm hover:shadow-md transition-all disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {saving ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span>{saving ? 'Saving…' : 'Save Changes'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* ── Account Section ───────────────────────────── */}
      <div className="bg-white rounded-2xl border border-[#E2E8F0] shadow-xs p-6 sm:p-8 space-y-4">
        <h2 className="text-base font-bold text-[#0F172A] pb-4 border-b border-[#E2E8F0]">Account</h2>

        <div className="flex items-center justify-between py-2">
          <div>
            <p className="text-sm font-semibold text-[#0F172A]">Sign Out</p>
            <p className="text-xs text-[#64748B]">Sign out of this CloudOps session.</p>
          </div>
          <button
            onClick={handleSignOut}
            className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-rose-50 hover:bg-rose-100 border border-rose-200 text-sm font-semibold text-rose-600 transition-all"
          >
            <LogOut className="w-4 h-4" />
            <span>Sign Out</span>
          </button>
        </div>
      </div>

      {/* ── Toast notification ─────────────────────────── */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50">
          <Toast msg={toast.msg} type={toast.type} onDismiss={() => setToast(null)} />
        </div>
      )}
    </div>
  );
}
