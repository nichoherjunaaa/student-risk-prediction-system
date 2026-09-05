import React from "react";
import { Link } from "react-router-dom";

// Satu-satunya sumber ukuran, warna, dan radius tombol aksi di aplikasi ini.
// Sebelumnya setiap halaman menuliskan kelasnya sendiri, sehingga tinggi dan
// sudut tombol berbeda-beda antar halaman untuk aksi yang setara.

const VARIANTS = {
  primary: "bg-primary text-white border-primary hover:bg-primary-dark",
  secondary: "bg-surface text-secondary border-border hover:bg-gray-50",
  outline: "bg-primary/5 text-primary border-primary/20 hover:bg-primary/10",
  ghost: "bg-transparent text-gray-600 border-transparent shadow-none hover:bg-gray-100",
  danger: "bg-red-600 text-white border-red-700 hover:bg-red-700",
};

const SIZES = {
  sm: "px-3 py-1.5 text-xs gap-1.5",
  md: "px-5 py-2.5 text-sm gap-2",
  lg: "px-6 py-3 text-sm gap-2",
};

const BASE =
  "inline-flex items-center justify-center whitespace-nowrap border font-bold rounded-lg " +
  "shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30 " +
  "focus:ring-offset-1 disabled:opacity-50 disabled:pointer-events-none";

function buttonClasses({ variant = "primary", size = "md", block = false, className = "" }) {
  return [
    BASE,
    VARIANTS[variant] || VARIANTS.primary,
    SIZES[size] || SIZES.md,
    block ? "w-full" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");
}

export function ButtonLink({ variant, size, block, className, ...props }) {
  return <Link className={buttonClasses({ variant, size, block, className })} {...props} />;
}

const Button = ({ variant, size, block, className, type = "button", ...props }) => (
  <button type={type} className={buttonClasses({ variant, size, block, className })} {...props} />
);

export default Button;
