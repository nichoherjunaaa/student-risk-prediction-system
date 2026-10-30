import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { clearSession } from '../lib/session';
import { LogOut, Clock } from 'lucide-react';
import Button from './Button';

const COUNTDOWN_SECONDS = 30;
// Lingkaran hitung mundur (SVG): keliling dipakai untuk strokeDasharray.
const RING_RADIUS = 34;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

const SessionTimeout = () => {
  const [isIdle, setIsIdle] = useState(false);
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const timerRef = useRef(null);
  const countdownRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();

  // Inactivity threshold (e.g., 10 minutes = 10 * 60 * 1000)
  const IDLE_TIMEOUT = 10 * 60 * 1000;
  
  const resetTimer = () => {
    // Only track idle if user is logged in (not on login, 404, or 500)
    if (location.pathname === '/login' || location.pathname === '/500' || isIdle) return;

    if (timerRef.current) clearTimeout(timerRef.current);
    
    timerRef.current = setTimeout(() => {
      setIsIdle(true);
      setCountdown(COUNTDOWN_SECONDS);
    }, IDLE_TIMEOUT);
  };

  useEffect(() => {
    // Check if user is logged in
    const user = localStorage.getItem('user');
    if (!user && location.pathname !== '/login') return;

    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'];
    events.forEach((event) => document.addEventListener(event, resetTimer));

    resetTimer();

    return () => {
      events.forEach((event) => document.removeEventListener(event, resetTimer));
      if (timerRef.current) clearTimeout(timerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [location.pathname, isIdle]);

  useEffect(() => {
    if (isIdle) {
      countdownRef.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            handleLogout();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [isIdle]);

  const handleLogout = () => {
    if (countdownRef.current) clearInterval(countdownRef.current);
    clearSession();
    setIsIdle(false);
    navigate('/login');
  };

  const handleStayLoggedIn = () => {
    setIsIdle(false);
    resetTimer();
  };

  if (!isIdle) return null;

  const sisa = countdown / COUNTDOWN_SECONDS;

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="session-timeout-title"
      aria-describedby="session-timeout-desc"
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
    >
      <div className="bg-surface rounded-2xl shadow-xl border border-border w-full max-w-md p-6 animate-in zoom-in-95 duration-200">
        <div className="flex flex-col items-center text-center">
          <div className="relative h-20 w-20 mb-4">
            <svg className="h-20 w-20 -rotate-90" viewBox="0 0 80 80" aria-hidden="true">
              <circle cx="40" cy="40" r={RING_RADIUS} fill="none" strokeWidth="6" className="stroke-amber-100" />
              <circle
                cx="40"
                cy="40"
                r={RING_RADIUS}
                fill="none"
                strokeWidth="6"
                strokeLinecap="round"
                strokeDasharray={RING_LENGTH}
                strokeDashoffset={RING_LENGTH * (1 - sisa)}
                className="stroke-amber-500 transition-[stroke-dashoffset] duration-1000 ease-linear"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-bold text-secondary leading-none tabular-nums">{countdown}</span>
              <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400 mt-0.5">detik</span>
            </div>
          </div>

          <h3 id="session-timeout-title" className="text-xl font-bold text-secondary mb-2 flex items-center gap-2">
            <Clock size={20} className="text-amber-500" /> Sesi Akan Berakhir
          </h3>
          <p id="session-timeout-desc" className="text-sm text-gray-600 mb-6 max-w-xs">
            Tidak ada aktivitas selama {IDLE_TIMEOUT / 60000} menit. Anda akan keluar otomatis dalam{" "}
            <span className="font-semibold text-secondary">{countdown} detik</span>.
          </p>

          <div className="flex gap-3 w-full">
            <Button variant="secondary" size="lg" block onClick={handleLogout}>
              <LogOut size={16} /> Keluar
            </Button>
            <Button size="lg" block onClick={handleStayLoggedIn} autoFocus>
              Tetap Masuk
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SessionTimeout;
