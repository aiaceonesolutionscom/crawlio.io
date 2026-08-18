import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldIcon, EyeIcon, EyeOffIcon } from 'lucide-react';
import { adminLogin } from '../lib/api/admin/auth';

const ADMIN_TOKEN_KEY = 'crawlio_admin_token';

export function AdminLogin() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await adminLogin(username, password);
      localStorage.setItem(ADMIN_TOKEN_KEY, res.token);
      navigate('/admin/super-admin');
    } catch (err: any) {
      setError(err?.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-ink-950">
      <div className="w-full max-w-[400px] px-5">
        <div className="flex flex-col items-center mb-8">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-signal/10 border border-signal/20">
            <ShieldIcon className="h-7 w-7 text-signal" />
          </div>
          <h1 className="mt-5 font-display text-[28px] font-semibold text-chalk">Admin Panel</h1>
          <p className="mt-2 text-[14px] text-chalk-dim">Enter your credentials to access the admin dashboard.</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-[13px] font-medium text-chalk-dim">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              className="h-11 w-full rounded-lg border border-ink-700 bg-ink-900 px-4 text-[15px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none focus:ring-1 focus:ring-signal/30"
              placeholder="admin"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-[13px] font-medium text-chalk-dim">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="h-11 w-full rounded-lg border border-ink-700 bg-ink-900 px-4 text-[15px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none focus:ring-1 focus:ring-signal/30"
                placeholder="Enter password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-chalk-dim hover:text-signal"
              >
                {showPassword ? <EyeOffIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {error && (
            <p className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-2.5 text-[13px] text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-1 h-12 rounded-lg bg-signal text-signal-deep text-[15px] font-semibold transition-colors hover:bg-signal-dark disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}