import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { LogOut, CheckCircle } from 'lucide-react';

const SessionTimeout = () => {
  const [isIdle, setIsIdle] = useState(false);
  const [countdown, setCountdown] = useState(30); // 30 seconds countdown
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
      setCountdown(30);
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
    localStorage.removeItem('user');
    setIsIdle(false);
    navigate('/login');
  };

  const handleStayLoggedIn = () => {
    setIsIdle(false);
    resetTimer();
  };

  if (!isIdle) return null;

  return (
    <div className="fixed inset-0 bg-black/60 z-[9999] flex items-center justify-center p-4 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full p-6 text-center animate-in zoom-in-95 duration-200">
        <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <span className="text-yellow-600 font-bold text-2xl">{countdown}</span>
        </div>
        <h3 className="text-xl font-bold text-gray-800 mb-2">Sesi Berakhir?</h3>
        <p className="text-gray-500 text-sm mb-6">
          Tidak ada aktivitas yang terdeteksi selama beberapa waktu. Apakah Anda ingin tetap login?
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={handleLogout}
            className="flex-1 flex justify-center items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 font-semibold rounded-lg hover:bg-gray-200 transition"
          >
            <LogOut size={16} /> Keluar
          </button>
          <button
            onClick={handleStayLoggedIn}
            className="flex-1 flex justify-center items-center gap-2 px-4 py-2 bg-primary text-white font-semibold rounded-lg hover:bg-primary-dark transition"
          >
            <CheckCircle size={16} /> Ya, Tetap Login
          </button>
        </div>
      </div>
    </div>
  );
};

export default SessionTimeout;
