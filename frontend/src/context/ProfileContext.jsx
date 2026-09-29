import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { supabase, isSupabaseConfigured } from '../lib/supabaseClient';
import { useAuth } from './AuthContext';

const ProfileContext = createContext();

export const ProfileProvider = ({ children }) => {
  const { user } = useAuth();
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [uploadLoading, setUploadLoading] = useState(false);

  // ─── Load profile from Supabase or local cache ───────────────────────────
  const loadProfile = useCallback(async () => {
    if (!user) {
      setProfile(null);
      setProfileLoading(false);
      return;
    }

    // Baseline profile derived from authenticated user
    const baseProfile = {
      id: user.id,
      display_name: user.name || (user.email ? user.email.split('@')[0] : 'Cloud Engineer'),
      role: user.role || 'Cloud Operations Specialist',
      avatar_url: null,
      email: user.email || '',
    };

    // Check local persistent storage cache per user ID for zero-flicker loading
    const cacheKey = `cloudops_profile_${user.id}`;
    const cachedStr = localStorage.getItem(cacheKey);

    if (cachedStr) {
      try {
        const parsed = JSON.parse(cachedStr);
        setProfile({ ...baseProfile, ...parsed });
      } catch (e) {
        setProfile(baseProfile);
      }
    } else {
      setProfile(baseProfile);
    }

    if (!isSupabaseConfigured() || !supabase) {
      setProfileLoading(false);
      return;
    }

    try {
      // Fetch user profile from Supabase profiles table
      const { data, error } = await supabase
        .from('profiles')
        .select('id, display_name, role, avatar_url, updated_at')
        .eq('id', user.id)
        .maybeSingle();

      if (error && error.code !== 'PGRST116') {
        console.warn('[ProfileContext] Profiles fetch warning:', error.message);
      }

      if (data) {
        const merged = { ...baseProfile, ...data };
        setProfile(merged);
        localStorage.setItem(cacheKey, JSON.stringify({
          display_name: merged.display_name,
          role: merged.role,
          avatar_url: merged.avatar_url,
        }));
      } else {
        // First login — upsert profile row into Supabase
        const newProfileData = {
          id: user.id,
          display_name: baseProfile.display_name,
          role: baseProfile.role,
          avatar_url: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };

        const { error: upsertErr } = await supabase.from('profiles').upsert(newProfileData, { onConflict: 'id' });
        if (upsertErr) {
          console.warn('[ProfileContext] Profile upsert warning:', upsertErr.message);
        }

        setProfile(baseProfile);
        localStorage.setItem(cacheKey, JSON.stringify({
          display_name: baseProfile.display_name,
          role: baseProfile.role,
          avatar_url: null,
        }));
      }
    } catch (err) {
      console.warn('[ProfileContext] Supabase profile sync warning:', err.message);
    } finally {
      setProfileLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  // ─── Update profile details (display_name & role) ────────────────────────
  const updateProfile = async ({ display_name, role }) => {
    if (!user || !profile) return { success: false, message: 'Not authenticated' };

    const updated = {
      ...profile,
      display_name: display_name.trim(),
      role: role.trim(),
      updated_at: new Date().toISOString(),
    };

    setProfile(updated);

    const cacheKey = `cloudops_profile_${user.id}`;
    localStorage.setItem(cacheKey, JSON.stringify({
      display_name: updated.display_name,
      role: updated.role,
      avatar_url: profile.avatar_url,
    }));

    if (!isSupabaseConfigured() || !supabase) {
      return { success: true };
    }

    try {
      const { error } = await supabase.from('profiles').upsert({
        id: user.id,
        display_name: updated.display_name,
        role: updated.role,
        avatar_url: profile.avatar_url,
        updated_at: new Date().toISOString(),
      }, { onConflict: 'id' });

      if (error) throw error;
      return { success: true };
    } catch (err) {
      console.warn('[ProfileContext] Supabase profile update error:', err.message);
      return { success: true, warning: 'Saved locally, Supabase sync failed.' };
    }
  };

  // ─── Upload avatar photo ─────────────────────────────────────────────────
  const uploadAvatar = async (file) => {
    if (!user || !file) return { success: false, message: 'No file provided' };
    setUploadLoading(true);

    try {
      let avatar_url = null;

      // 1. Convert file to base64 Data URL for instant local display & fallback
      const reader = new FileReader();
      const base64Data = await new Promise((res, rej) => {
        reader.onload = () => res(reader.result);
        reader.onerror = rej;
        reader.readAsDataURL(file);
      });

      avatar_url = base64Data;

      // 2. Try Supabase Storage upload if available
      if (isSupabaseConfigured() && supabase) {
        try {
          const ext = file.name.split('.').pop();
          const path = `${user.id}/avatar.${ext}`;

          const { error: uploadErr } = await supabase.storage
            .from('avatars')
            .upload(path, file, { upsert: true, contentType: file.type });

          if (!uploadErr) {
            const { data: urlData } = supabase.storage.from('avatars').getPublicUrl(path);
            if (urlData?.publicUrl) {
              avatar_url = urlData.publicUrl + `?t=${Date.now()}`;
            }
          }
        } catch (stgErr) {
          console.warn('[ProfileContext] Storage upload fallback to data URL:', stgErr.message);
        }
      }

      // Update state & local cache
      const updated = { ...profile, avatar_url };
      setProfile(updated);

      const cacheKey = `cloudops_profile_${user.id}`;
      localStorage.setItem(cacheKey, JSON.stringify({
        display_name: profile.display_name,
        role: profile.role,
        avatar_url,
      }));

      if (isSupabaseConfigured() && supabase) {
        await supabase.from('profiles').upsert({
          id: user.id,
          display_name: profile.display_name,
          role: profile.role,
          avatar_url,
          updated_at: new Date().toISOString(),
        }, { onConflict: 'id' });
      }

      return { success: true, url: avatar_url };
    } catch (err) {
      return { success: false, message: err.message || 'Avatar upload failed' };
    } finally {
      setUploadLoading(false);
    }
  };

  // ─── Remove avatar photo ─────────────────────────────────────────────────
  const removeAvatar = async () => {
    if (!user || !profile) return;

    const updated = { ...profile, avatar_url: null };
    setProfile(updated);

    const cacheKey = `cloudops_profile_${user.id}`;
    localStorage.setItem(cacheKey, JSON.stringify({
      display_name: profile.display_name,
      role: profile.role,
      avatar_url: null,
    }));

    if (isSupabaseConfigured() && supabase) {
      try {
        await supabase.from('profiles').upsert({
          id: user.id,
          display_name: profile.display_name,
          role: profile.role,
          avatar_url: null,
          updated_at: new Date().toISOString(),
        }, { onConflict: 'id' });
      } catch (err) {
        console.warn('[ProfileContext] Remove avatar Supabase warning:', err.message);
      }
    }
  };

  // ─── Compute initials dynamically from display_name ─────────────────────
  const initials = (profile?.display_name || user?.name || user?.email || 'Cloud Operator')
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() || '')
    .join('') || 'CO';

  return (
    <ProfileContext.Provider
      value={{
        profile,
        profileLoading,
        uploadLoading,
        initials,
        updateProfile,
        uploadAvatar,
        removeAvatar,
        reload: loadProfile,
      }}
    >
      {children}
    </ProfileContext.Provider>
  );
};

export const useProfile = () => useContext(ProfileContext);
