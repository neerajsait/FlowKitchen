// Custom inline SVG icon set (24px grid, 1.7px strokes).
// Replaces the third-party icon dependency with a consistent in-house set.

import React from "react";

const S = ({ size = 20, children, ...rest }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24"
    fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true" focusable="false" {...rest}>{children}</svg>
);


export const Archive = (p) => <S {...p}><rect x="3.5" y="4" width="17" height="4.5" rx="0.8"/><path d="M5.5 8.5V19a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1V8.5"/><path d="M10 12.5h4"/></S>;

export const AlertCircle = (p) => <S {...p}><circle cx="12" cy="12" r="9"/><line x1="12" y1="7.5" x2="12" y2="13"/><circle cx="12" cy="16.6" r="0.4" fill="currentColor"/></S>;

export const AlertTriangle = (p) => <S {...p}><path d="M10.3 4.2 2.9 17.1a2 2 0 0 0 1.7 3h14.8a2 2 0 0 0 1.7-3L13.7 4.2a2 2 0 0 0-3.4 0Z"/><line x1="12" y1="9.5" x2="12" y2="14"/><circle cx="12" cy="17" r="0.4" fill="currentColor"/></S>;

export const ArrowLeft = (p) => <S {...p}><path d="M19 12H5"/><path d="m11 18-6-6 6-6"/></S>;

export const ArrowRight = (p) => <S {...p}><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></S>;

export const Award = (p) => <S {...p}><circle cx="12" cy="9" r="5.5"/><path d="M8.8 13.5 7.5 21l4.5-2.6L16.5 21l-1.3-7.5"/></S>;

export const Banknote = (p) => <S {...p}><rect x="2.5" y="6.5" width="19" height="11" rx="1.5"/><circle cx="12" cy="12" r="2.6"/><path d="M6 10v4M18 10v4"/></S>;

export const BarChart3 = (p) => <S {...p}><path d="M4 20V10M10 20V4M16 20v-8M20 20H4"/></S>;

export const BookOpen = (p) => <S {...p}><path d="M12 6.5C10.5 5 8.4 4.5 5.5 4.5c-.8 0-1.5.1-2 .2V18c.5-.1 1.2-.2 2-.2 2.9 0 5 .6 6.5 2 1.5-1.4 3.6-2 6.5-2 .8 0 1.5.1 2 .2V4.7c-.5-.1-1.2-.2-2-.2-2.9 0-5 .5-6.5 2Z"/><path d="M12 6.5V20"/></S>;

export const Calendar = (p) => <S {...p}><rect x="3.5" y="5" width="17" height="15.5" rx="1.5"/><path d="M8 3v4M16 3v4M3.5 10h17"/></S>;

export const Check = (p) => <S {...p}><path d="m5 12.5 4.5 4.5L19 7.5"/></S>;

export const CheckCircle = (p) => <S {...p}><circle cx="12" cy="12" r="9"/><path d="m8 12.3 2.7 2.7L16 9.5"/></S>;

export const ChefHat = (p) => <S {...p}><path d="M7 21h10M6.5 17.5h11"/><path d="M6.5 17.5v-3.2A4.6 4.6 0 0 1 4 9.9a4.4 4.4 0 0 1 3-4.2A5.2 5.2 0 0 1 12 2.5a5.2 5.2 0 0 1 5 3.2 4.4 4.4 0 0 1 3 4.2 4.6 4.6 0 0 1-2.5 4.4v3.2"/></S>;

export const ChevronDown = (p) => <S {...p}><path d="m6 9.5 6 6 6-6"/></S>;

export const ChevronLeft = (p) => <S {...p}><path d="m14.5 6-6 6 6 6"/></S>;

export const ChevronRight = (p) => <S {...p}><path d="m9.5 6 6 6-6 6"/></S>;

export const ChevronUp = (p) => <S {...p}><path d="m6 14.5 6-6 6 6"/></S>;

export const Clock = (p) => <S {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/></S>;

export const CreditCard = (p) => <S {...p}><rect x="2.5" y="5.5" width="19" height="13" rx="1.8"/><path d="M2.5 10h19"/></S>;

export const Download = (p) => <S {...p}><path d="M12 4v11M7.5 11l4.5 4.5L16.5 11"/><path d="M4.5 19.5h15"/></S>;

export const Edit2 = (p) => <S {...p}><path d="M15.2 4.6a2.1 2.1 0 0 1 3 3L8 17.8l-4 1 1-4Z"/><path d="M13.5 6.3l3 3"/></S>;

export const Edit3 = (p) => <S {...p}><path d="M15.2 4.6a2.1 2.1 0 0 1 3 3L8 17.8l-4 1 1-4Z"/><path d="M13.5 6.3l3 3M4 21h9"/></S>;

export const Eye = (p) => <S {...p}><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.8"/></S>;

export const EyeOff = (p) => <S {...p}><path d="M10 5.9A9.9 9.9 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-2.8 3.7M6.6 6.9A16.6 16.6 0 0 0 2.5 12S6 18.5 12 18.5a9.7 9.7 0 0 0 5.3-1.6"/><path d="M3 3l18 18"/><path d="M9.9 9.9a2.8 2.8 0 0 0 4 4"/></S>;

export const FileText = (p) => <S {...p}><path d="M6 2.5h7.5L19 8v13.5H6Z"/><path d="M13.5 2.5V8H19"/><path d="M9 12h6M9 15.5h6"/></S>;

export const Flame = (p) => <S {...p}><path d="M12 21.5c3.6 0 6-2.3 6-5.6 0-2.4-1.4-4.3-2.8-5.9C13.8 8.4 13 6.8 13 4.5c-3 2-4.1 4.6-4.3 6.7-.9-.6-1.4-1.5-1.6-2.7-1.4 1.7-2.1 3.6-2.1 5.4 0 3.3 3.4 7.6 7 7.6Z"/></S>;

export const Gift = (p) => <S {...p}><rect x="3.5" y="8.5" width="17" height="4"/><rect x="5" y="12.5" width="14" height="8.5"/><path d="M12 8.5v12.5"/><path d="M12 8.5s-1-5.5-4-5.5a2.2 2.2 0 0 0 0 4.4ZM12 8.5s1-5.5 4-5.5a2.2 2.2 0 0 1 0 4.4Z"/></S>;

export const Globe = (p) => <S {...p}><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></S>;

export const Grid = (p) => <S {...p}><rect x="3.5" y="3.5" width="7" height="7" rx="0.8"/><rect x="13.5" y="3.5" width="7" height="7" rx="0.8"/><rect x="3.5" y="13.5" width="7" height="7" rx="0.8"/><rect x="13.5" y="13.5" width="7" height="7" rx="0.8"/></S>;

export const Heart = (p) => <S {...p}><path d="M12 20.5S3.5 15.5 3.5 9.3A4.6 4.6 0 0 1 12 6.6a4.6 4.6 0 0 1 8.5 2.7c0 6.2-8.5 11.2-8.5 11.2Z"/></S>;

export const Home = (p) => <S {...p}><path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1Z"/></S>;

export const Image = (p) => <S {...p}><rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><circle cx="9" cy="9.5" r="1.6"/><path d="m4.5 17 4.5-4.5 3 3 3.5-3.5 4 4"/></S>;

export const IndianRupee = (p) => <S {...p}><path d="M7 4.5h10M7 8.75h10M15.5 4.5c0 4.4-3.6 6.4-8.5 6.4 3.4.4 6.6 2.4 8.5 6.6M8 11.2 16 20"/></S>;

export const KeyRound = (p) => <S {...p}><circle cx="8" cy="15.5" r="4.5"/><path d="m11.2 12.3 8.3-8.3M17 6.5l2.5 2.5M14.5 9l2 2"/></S>;

export const Leaf = (p) => <S {...p}><path d="M20 4.5C11 4.5 4.5 9 4.5 16.5c0 1.2.2 2.3.5 3C13.5 19.5 20 13 20 4.5Z"/><path d="M5 19.5C8 14 12 10.5 16.5 8.5"/></S>;

export const Loader2 = (p) => <S {...p}><path d="M21 12a9 9 0 1 1-9-9"/></S>;

export const Lock = (p) => <S {...p}><rect x="5" y="10.5" width="14" height="10.5" rx="1.5"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/></S>;

export const LogIn = (p) => <S {...p}><path d="M9 3.5h9a1.5 1.5 0 0 1 1.5 1.5v14a1.5 1.5 0 0 1-1.5 1.5H9"/><path d="m13 12H3.5M9.5 8 13 12l-3.5 4"/></S>;

export const LogOut = (p) => <S {...p}><path d="M15 3.5H6A1.5 1.5 0 0 0 4.5 5v14A1.5 1.5 0 0 0 6 20.5h9"/><path d="m16 8 4 4-4 4M20 12H9.5"/></S>;

export const Mail = (p) => <S {...p}><rect x="2.5" y="5" width="19" height="14" rx="1.5"/><path d="m3 6.5 9 6.5 9-6.5"/></S>;

export const MapPin = (p) => <S {...p}><path d="M12 21.5s7-5.8 7-11.5a7 7 0 0 0-14 0c0 5.7 7 11.5 7 11.5Z"/><circle cx="12" cy="10" r="2.6"/></S>;

export const Megaphone = (p) => <S {...p}><path d="M4 10v4a1 1 0 0 0 1 1h2.5L18 19.5v-15L7.5 9H5a1 1 0 0 0-1 1Z"/><path d="M7.5 15v4.5"/><path d="M20.5 9.5a4 4 0 0 1 0 5"/></S>;

export const MessageCircle = (p) => <S {...p}><path d="M21 11.8A8.4 8.4 0 0 1 12.6 20 8.9 8.9 0 0 1 8 18.8L3 20l1.3-4.9A8.3 8.3 0 0 1 3.4 11.8 8.4 8.4 0 0 1 11.8 3.5 8.4 8.4 0 0 1 21 11.8Z"/></S>;

export const MessageSquare = (p) => <S {...p}><path d="M20.5 15.5a1.5 1.5 0 0 1-1.5 1.5H8l-4.5 4V5A1.5 1.5 0 0 1 5 3.5h14a1.5 1.5 0 0 1 1.5 1.5Z"/></S>;

export const Minus = (p) => <S {...p}><path d="M5 12h14"/></S>;

export const Package = (p) => <S {...p}><path d="m12 2.8 8 4v10.4l-8 4-8-4V6.8Z"/><path d="m4 6.8 8 4 8-4M12 10.8v10.4M8 4.8l8 4"/></S>;

export const Paperclip = (p) => <S {...p}><path d="m20 11.5-7.8 7.8a5 5 0 0 1-7-7L13 4.5a3.3 3.3 0 0 1 4.7 4.7l-7.6 7.6a1.7 1.7 0 0 1-2.4-2.4l7-7"/></S>;

export const Plus = (p) => <S {...p}><path d="M12 5v14M5 12h14"/></S>;

export const Printer = (p) => <S {...p}><path d="M7 8V3.5h10V8"/><rect x="3.5" y="8" width="17" height="8.5" rx="1"/><rect x="7" y="14" width="10" height="6.5"/></S>;

export const QrCode = (p) => <S {...p}><rect x="3.5" y="3.5" width="7" height="7"/><rect x="13.5" y="3.5" width="7" height="7"/><rect x="3.5" y="13.5" width="7" height="7"/><path d="M13.5 13.5h3v3h-3zM20.5 13.5v3M17 20.5h3.5"/></S>;

export const Receipt = (p) => <S {...p}><path d="M5 21.5V3.5h14v18l-2.3-1.6-2.4 1.6-2.3-1.6-2.3 1.6L7.3 19.9Z"/><path d="M9 8h6M9 12h6"/></S>;

export const RefreshCcw = (p) => <S {...p}><path d="M3.5 8.5A9.5 9.5 0 0 1 20 10M20.5 15.5A9.5 9.5 0 0 1 4 14"/><path d="M20 4v6h-6M4 20v-6h6"/></S>;

export const RefreshCw = (p) => <S {...p}><path d="M20.5 8.5A9.5 9.5 0 0 0 4 10M3.5 15.5A9.5 9.5 0 0 0 20 14"/><path d="M4 4v6h6M20 20v-6h-6"/></S>;

export const RotateCcw = (p) => <S {...p}><path d="M3.5 4v6h6"/><path d="M4.2 14.5A8.5 8.5 0 1 0 6 6.2L3.5 10"/></S>;

export const ScanLine = (p) => <S {...p}><path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16"/><path d="M4 12h16"/></S>;

export const Search = (p) => <S {...p}><circle cx="11" cy="11" r="7"/><path d="m16 16 4.5 4.5"/></S>;

export const Settings = (p) => <S {...p}><circle cx="12" cy="12" r="3.2"/><path d="M12 2.8v3M12 18.2v3M2.8 12h3M18.2 12h3M5.5 5.5l2.1 2.1M16.4 16.4l2.1 2.1M18.5 5.5l-2.1 2.1M7.6 16.4l-2.1 2.1"/></S>;

export const Share2 = (p) => <S {...p}><circle cx="6" cy="12" r="2.5"/><circle cx="17.5" cy="5.5" r="2.5"/><circle cx="17.5" cy="18.5" r="2.5"/><path d="m8.3 10.8 6.9-4M8.3 13.2l6.9 4"/></S>;

export const Shield = (p) => <S {...p}><path d="M12 2.8 4.5 5.5v6c0 5 3.2 8 7.5 9.7 4.3-1.7 7.5-4.7 7.5-9.7v-6Z"/></S>;

export const ShieldAlert = (p) => <S {...p}><path d="M12 2.8 4.5 5.5v6c0 5 3.2 8 7.5 9.7 4.3-1.7 7.5-4.7 7.5-9.7v-6Z"/><line x1="12" y1="8" x2="12" y2="12.5"/><circle cx="12" cy="15.5" r="0.4" fill="currentColor"/></S>;

export const ShieldCheck = (p) => <S {...p}><path d="M12 2.8 4.5 5.5v6c0 5 3.2 8 7.5 9.7 4.3-1.7 7.5-4.7 7.5-9.7v-6Z"/><path d="m8.7 11.8 2.4 2.4 4.4-4.4"/></S>;

export const ShoppingBag = (p) => <S {...p}><path d="M5.5 7.5h13l-1 13h-11Z"/><path d="M9 10V6.5a3 3 0 0 1 6 0V10"/></S>;

export const ShoppingCart = (p) => <S {...p}><circle cx="9" cy="20" r="1.4"/><circle cx="17.5" cy="20" r="1.4"/><path d="M2.5 3.5H5l2.6 12h10.9l2.5-8.5H6"/></S>;

export const SlidersHorizontal = (p) => <S {...p}><path d="M4 7.5h9M17 7.5h3M4 16.5h3M11 16.5h9"/><circle cx="15" cy="7.5" r="2"/><circle cx="9" cy="16.5" r="2"/></S>;

export const Sparkles = (p) => <S {...p}><path d="M12 4.5 13.8 10 19.5 12l-5.7 2L12 19.5 10.2 14 4.5 12l5.7-2Z"/></S>;

export const Star = (p) => <S {...p}><path d="m12 3.4 2.6 5.3 5.9.9-4.3 4.1 1 5.9-5.2-2.8-5.2 2.8 1-5.9L3.5 9.6l5.9-.9Z"/></S>;

export const StarHalf = (p) => <S {...p}><path d="m12 3.4 2.6 5.3 5.9.9-4.3 4.1 1 5.9-5.2-2.8-5.2 2.8 1-5.9L3.5 9.6l5.9-.9Z"/><path d="M12 3.4v13.4l-5.2 2.8 1-5.9L3.5 9.6l5.9-.9Z" fill="currentColor"/></S>;

export const Store = (p) => <S {...p}><path d="M4 9.5 5.5 4h13L20 9.5M4 9.5a2.6 2.6 0 0 0 5.3 0 2.65 2.65 0 0 0 5.3 0 2.6 2.6 0 0 0 5.4 0M5 12.2V20h14v-7.8M9.5 20v-5h5v5"/></S>;

export const Tag = (p) => <S {...p}><path d="M3.5 12.6V4.5a1 1 0 0 1 1-1h8.1a1.5 1.5 0 0 1 1.1.4l7 7.1a1.5 1.5 0 0 1 0 2.1l-6.7 6.7a1.5 1.5 0 0 1-2.1 0l-7-7a1.5 1.5 0 0 1-.4-1.1Z"/><circle cx="8" cy="8" r="1.4"/></S>;

export const Trash2 = (p) => <S {...p}><path d="M4 6.5h16M9.5 6.5V4h5v2.5M6 6.5l1 14h10l1-14"/><path d="M10 10.5v6M14 10.5v6"/></S>;

export const TrendingUp = (p) => <S {...p}><path d="m3.5 17 5.5-5.5 3.5 3.5 7.5-7.5"/><path d="M15.5 7.5H20V12"/></S>;

export const Truck = (p) => <S {...p}><path d="M2.5 6h11v11h-11Z"/><path d="M13.5 10h4l3 3.5V17h-7"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/></S>;

export const User = (p) => <S {...p}><circle cx="12" cy="8" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/></S>;

export const UserPlus = (p) => <S {...p}><circle cx="10" cy="8" r="3.8"/><path d="M3.5 20a6.8 6.8 0 0 1 13 0"/><path d="M18.5 7.5v5M16 10h5"/></S>;

export const Users = (p) => <S {...p}><circle cx="9" cy="8.5" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 5.6a3.5 3.5 0 0 1 0 6.8M17.8 14.3a6.5 6.5 0 0 1 3.7 5.7"/></S>;

export const Volume2 = (p) => <S {...p}><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4Z"/><path d="M15.5 9a4.5 4.5 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11"/></S>;

export const VolumeX = (p) => <S {...p}><path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4Z"/><path d="m16.5 9.5 5 5M21.5 9.5l-5 5"/></S>;

export const Wallet = (p) => <S {...p}><path d="M20.5 8V6a1.5 1.5 0 0 0-1.5-1.5H4A1.5 1.5 0 0 0 2.5 6v12A1.5 1.5 0 0 0 4 19.5h15a1.5 1.5 0 0 0 1.5-1.5V8Z"/><path d="M20.5 8h-18M16.5 13.75h.01"/></S>;

export const X = (p) => <S {...p}><path d="M6 6l12 12M18 6 6 18"/></S>;

export const XCircle = (p) => <S {...p}><circle cx="12" cy="12" r="9"/><path d="m9 9 6 6M15 9l-6 6"/></S>;

export const Zap = (p) => <S {...p}><path d="M13 2.5 4.5 13.5h6L11 21.5l8.5-11h-6Z"/></S>;
