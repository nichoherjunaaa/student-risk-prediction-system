import React, { useState, useEffect } from "react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import AutoPredictCard from "../components/AutoPredictCard";
import { useProdiScope } from "../lib/prodi";
import { useNavigate } from "react-router-dom";

const Upload = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictProgress, setPredictProgress] = useState(0);
  const [prodi, setProdi] = useState("");
  const { list: prodiList, locked: lockedProdi } = useProdiScope();
  const navigate = useNavigate();

  // Dosen yang terikat prodi tidak memilih prodi; nilainya diisi otomatis.
  useEffect(() => {
    if (lockedProdi) setProdi(lockedProdi);
  }, [lockedProdi]);

  // Progress bar + navigasi ke halaman hasil setelah prediksi selesai.
  const runWithProgress = async (request, onError) => {
    setIsPredicting(true);
    setPredictProgress(5);
    // Animasi progress bar palsu agar UI terasa interaktif saat backend menghitung matriks CNN
    const progressInterval = setInterval(() => {
      setPredictProgress((prev) => {
        if (prev >= 90) return prev;
        return prev + Math.floor(Math.random() * 8) + 4;
      });
    }, 400);
    try {
      const response = await request();
      clearInterval(progressInterval);
      setPredictProgress(100);
      setTimeout(() => {
        setIsPredicting(false);
        setPredictProgress(0);
        navigate("/results", {
          state: { predictionData: response.data, prodi: response.data.prodi || prodi },
        });
      }, 500);
    } catch (err) {
      clearInterval(progressInterval);
      setPredictProgress(100);
      setTimeout(() => {
        setIsPredicting(false);
        setPredictProgress(0);
        const detail = err.response?.data;
        onError(
          (typeof detail === "object" ? detail?.error : null) ||
            "Gagal mengeksekusi prediksi pada berkas data baru Anda.",
        );
      }, 500);
    }
  };

  return (
    <div className="bg-background font-sans text-secondary antialiased h-screen flex flex-col lg:flex-row overflow-hidden">
      <Sidebar
        isOpen={sidebarOpen}
        toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />

      <div className="flex-1 flex flex-col overflow-y-auto">
        <Header
          toggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          title="Unggah Data"
          subtitle="Jalankan prediksi sisip program dari berkas di Berkas Mahasiswa."
        />

        <main className="p-6 space-y-6 max-w-[96rem] w-full mx-auto">
          <AutoPredictCard
            prodi={prodi}
            setProdi={setProdi}
            prodiList={prodiList}
            lockedProdi={lockedProdi}
            runWithProgress={runWithProgress}
          />
        </main>
      </div>

      {/* Progress Pop-Up Modal */}
      {isPredicting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface rounded-2xl shadow-xl border border-border px-8 py-6 flex flex-col items-center w-full max-w-md">
            <h3 className="text-lg font-bold text-secondary mb-4">
              Menjalankan prediksi, mohon tunggu...
            </h3>
            <div className="w-full bg-gray-200 rounded-full h-4 mb-2 overflow-hidden border border-gray-300">
              <div
                className="bg-primary h-4 rounded-full transition-all duration-300"
                style={{ width: `${predictProgress}%` }}
              ></div>
            </div>
            <p className="text-sm font-medium text-gray-600">
              {predictProgress}% Selesai
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
export default Upload;
