import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function CookieConsent() {
  const [showBanner, setShowBanner] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem('FoodPilot_cookie_consent');
    if (!consent) {
      // Small delay to ensure it doesn't jarringly appear on instant load
      const timer = setTimeout(() => setShowBanner(true), 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleAcceptAll = () => {
    localStorage.setItem('FoodPilot_cookie_consent', 'all');
    setShowBanner(false);
  };

  const handleEssentialOnly = () => {
    localStorage.setItem('FoodPilot_cookie_consent', 'essential');
    setShowBanner(false);
  };

  return (
    <AnimatePresence>
      {showBanner && (
        <motion.div
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          style={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            background: 'rgba(18, 22, 28, 0.95)',
            backdropFilter: 'blur(10px)',
            borderTop: '1px solid var(--border)',
            padding: '1.5rem',
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
            boxShadow: '0 -10px 40px rgba(0,0,0,0.3)',
          }}
        >
          <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 'bold', color: '#ffffff', marginBottom: '0.5rem' }}>
                We respect your privacy
              </h3>
              <p style={{ fontSize: '0.875rem', color: 'rgba(255, 255, 255, 0.7)', lineHeight: 1.5, margin: 0 }}>
                We use cookies to enhance your browsing experience, serve personalized ads or content, and analyze our traffic. By clicking "Accept All", you consent to our use of cookies.
              </p>
            </div>
            
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', justifyContent: 'flex-start' }}>
              <button 
                onClick={handleAcceptAll}
                className="btn btn-primary"
                style={{ padding: '0.75rem 1.5rem', fontWeight: 600, color: '#ffffff' }}
              >
                Accept All
              </button>
              <button 
                onClick={handleEssentialOnly}
                className="btn btn-secondary"
                style={{ padding: '0.75rem 1.5rem', background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', color: '#ffffff' }}
              >
                Essential Only
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
