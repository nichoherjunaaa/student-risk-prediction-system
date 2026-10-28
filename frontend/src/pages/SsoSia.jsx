import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, Loader2 } from "lucide-react";
import axios from "axios";
import { clearSession } from "../lib/session";
import { homePath } from "../lib/roles";
import { ButtonLink } from "../components/Button";

// Tujuan link masuk dari SIA: /sso/sia?id=&ts=&nonce=&sig=
// Parameternya diteruskan ke backend untuk diperiksa (lihat routes/sso.py).
const SsoSia = () => {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  // Link hanya sekali pakai: di StrictMode effect jalan dua kali, dan request
  // kedua akan ditolak sebagai replay.
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current) return;
    sent.current = true;

    const params = new URLSearchParams(window.location.search);
    const payload = {
      id: params.get("id"),
      ts: params.get("ts"),
      nonce: params.get("nonce"),
      sig: params.get("sig"),
    };
    // Hapus parameter dari address bar dan riwayat browser.
    window.history.replaceState(null, "", "/sso/sia");
    // Sesi user sebelumnya di browser ini tidak boleh tersisa, juga saat link
    // ditolak (mis. komputer bersama).
    clearSession();

    axios
      .post("/api/sso/sia", payload)
      .then((response) => {
        const user = response.data.user;
        localStorage.setItem("user", JSON.stringify(user));
        localStorage.setItem("token", response.data.token);
        navigate(homePath(user.role), { replace: true });
      })
      .catch((err) => {
        setError(
          err.response?.data?.error ||
            "Akses dari SIA tidak valid atau sudah kedaluwarsa.",
        );
      });
  }, [navigate]);

  return (
    <div className="bg-background min-h-screen flex items-center justify-center p-6 font-sans text-secondary antialiased">
      <div className="bg-surface max-w-md w-full p-8 rounded-2xl shadow-xl border border-border text-center">
        {error ? (
          <>
            <div className="w-20 h-20 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-6">
              <AlertCircle className="h-10 w-10 text-red-600" />
            </div>
            <h1 className="text-xl font-bold mb-3">Gagal Masuk dari SIA</h1>
            <p className="text-gray-500 mb-8 text-sm leading-relaxed">
              {error} Silakan buka kembali menu Sisip Program dari SIA, atau
              masuk lewat halaman login.
            </p>
            <ButtonLink to="/login" replace>
              Masuk lewat halaman login
            </ButtonLink>
          </>
        ) : (
          <>
            <Loader2 className="h-10 w-10 text-primary animate-spin mx-auto mb-6" />
            <p className="text-gray-500 text-sm">Memeriksa akses dari SIA...</p>
          </>
        )}
      </div>
    </div>
  );
};

export default SsoSia;
