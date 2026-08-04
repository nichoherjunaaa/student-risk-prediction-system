import React, { useState } from 'react';
import { ShieldCheck, User, Lock, AlertTriangle, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const Login = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await axios.post('http://localhost:5000/api/login', {
        email,
        password
      });

      const user = response.data.user;
      localStorage.setItem('user', JSON.stringify(user));

      if (user.role === 'admin') {
        navigate('/admin/model');
      } else {
        navigate('/upload');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Gagal terhubung ke server');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-5xl bg-surface rounded-2xl shadow-xl overflow-hidden flex flex-col md:flex-row min-h-[600px]">
        
        <div className="md:w-1/2 bg-primary p-12 flex flex-col items-center justify-center text-surface relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-2 bg-accent"></div>
          <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-primary-dark rounded-full opacity-50"></div>
          <div className="absolute -top-12 -right-12 w-48 h-48 bg-primary-dark rounded-full opacity-50"></div>
          
          <div className="relative z-10 flex flex-col items-center text-center">
            <img src="/logo.png" alt="Logo Sisip Program" className="h-24 w-24 mb-8 object-contain bg-surface p-3 rounded-2xl shadow-lg" />
            <h1 className="text-3xl font-bold mb-4 tracking-tight">Sisip Program</h1>
            <p className="text-lg text-white/80 font-medium max-w-sm">Sistem Prediksi Kelulusan & Evaluasi Akademik Mahasiswa</p>
            
            <div className="mt-12 flex items-center space-x-2 text-sm text-accent font-medium bg-primary-dark/40 px-4 py-2 rounded-full">
              <ShieldCheck className="h-4 w-4" />
              <span>Sistem Informasi Terpadu</span>
            </div>
          </div>
        </div>

        <div className="md:w-1/2 p-10 md:p-14 flex flex-col justify-center bg-surface">
          <div className="w-full max-w-md mx-auto">
            <h2 className="text-3xl font-bold text-secondary mb-2">Selamat Datang Kembali</h2>
            <p className="text-gray-500 mb-8">Silakan masuk untuk mengakses dasbor.</p>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center text-red-600 text-sm">
                <AlertTriangle className="h-4 w-4 mr-2" />
                {error}
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-6">
              <div>
                <label htmlFor="email" className="block text-sm font-semibold text-secondary mb-2">Email atau Nama Pengguna</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                    <User className="h-5 w-5" />
                  </div>
                  <input type="text" id="email" name="email" required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="block w-full pl-10 pr-3 py-3 border border-border rounded-lg text-secondary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition-colors bg-background/50 focus:bg-surface"
                    placeholder="Masukkan email (contoh: admin@... atau dpa@...)" />
                </div>
              </div>

              <div>
                <div className="flex justify-between mb-2">
                  <label htmlFor="password" className="block text-sm font-semibold text-secondary">Kata Sandi</label>
                  <a href="#" className="text-sm font-medium text-primary hover:text-primary-dark transition-colors">Lupa kata sandi?</a>
                </div>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                    <Lock className="h-5 w-5" />
                  </div>
                  <input type="password" id="password" name="password" required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="block w-full pl-10 pr-3 py-3 border border-border rounded-lg text-secondary focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary transition-colors bg-background/50 focus:bg-surface"
                    placeholder="Masukkan kata sandi Anda" />
                </div>
              </div>

              <div className="flex items-center">
                <input id="remember-me" name="remember-me" type="checkbox"
                  className="h-4 w-4 text-primary focus:ring-primary border-gray-300 rounded cursor-pointer accent-primary" />
                <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-600 cursor-pointer">
                  Ingat saya selama 30 hari
                </label>
              </div>

              <button type="submit" disabled={loading}
                className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-base font-semibold text-secondary bg-accent hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent transition-colors disabled:opacity-50">
                {loading ? <Loader2 className="animate-spin h-5 w-5" /> : 'Masuk'}
              </button>
            </form>
            
            <div className="mt-8 pt-6 border-t border-border text-center">
              <p className="text-sm text-gray-500">
                Butuh akses? <a href="#" className="font-medium text-primary hover:text-primary-dark transition-colors">Hubungi Administrator</a>
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default Login;
