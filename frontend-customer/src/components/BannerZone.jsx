import React, { useState, useEffect, useRef } from 'react';
import { api } from '../utils/api';
import './BannerZone.css';

const BannerZone = ({ zoneId, userId, onApplyCoupon }) => {
  const [banners, setBanners] = useState([]);
  const [loading, setLoading] = useState(true);
  const containerRef = useRef(null);
  
  // Track impressions
  const impressionsTracked = useRef(new Set());

  useEffect(() => {
    const fetchBanners = async () => {
      try {
        const data = await api.getPublicBanners(zoneId, userId);
        setBanners(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error("Failed to load banners for zone:", zoneId, err);
      } finally {
        setLoading(false);
      }
    };
    fetchBanners();
  }, [zoneId, userId]);

  useEffect(() => {
    if (loading || banners.length === 0) return;

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const bannerId = entry.target.dataset.id;
          if (bannerId && !impressionsTracked.current.has(bannerId)) {
            impressionsTracked.current.add(bannerId);
            api.trackBannerImpression(bannerId).catch(console.error);
          }
        }
      });
    }, { threshold: 0.5 });

    const bannerElements = document.querySelectorAll(`.banner-zone-${zoneId} .banner-item`);
    bannerElements.forEach(el => observer.observe(el));

    return () => observer.disconnect();
  }, [banners, loading, zoneId]);

  const handleBannerClick = async (banner) => {
    try {
      await api.trackBannerClick(banner.id);
    } catch (err) {
      console.error("Failed to track click", err);
    }
    
    if (banner.linked_coupon_code && onApplyCoupon) {
      onApplyCoupon(banner.linked_coupon_code);
    } else if (banner.target_url) {
      window.location.href = banner.target_url;
    }
  };

  if (loading || banners.length === 0) return null;

  return (
    <div className={`banner-zone-${zoneId} w-full flex flex-col gap-4 my-4`}>
      {banners.map(banner => (
        <BannerItem 
          key={banner.id} 
          banner={banner} 
          onClick={() => handleBannerClick(banner)} 
        />
      ))}
    </div>
  );
};

const BannerItem = ({ banner, onClick }) => {
  const [timeLeft, setTimeLeft] = useState(null);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    if (!banner.has_countdown || !banner.countdown_end_time) return;

    const calculateTimeLeft = () => {
      const difference = new Date(banner.countdown_end_time) - new Date();
      if (difference <= 0) {
        setExpired(true);
        return null;
      }
      return {
        hours: Math.floor((difference / (1000 * 60 * 60)) % 24),
        minutes: Math.floor((difference / 1000 / 60) % 60),
        seconds: Math.floor((difference / 1000) % 60)
      };
    };

    setTimeLeft(calculateTimeLeft());

    const timer = setInterval(() => {
      const remaining = calculateTimeLeft();
      if (!remaining) {
        clearInterval(timer);
      } else {
        setTimeLeft(remaining);
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [banner]);

  if (expired) return null;

  // Render logic based on style
  const getStyleClasses = () => {
    switch(banner.display_style) {
      case 'pill_text':
        return 'rounded-full w-full h-16 flex items-center justify-center bg-gray-900 text-white shadow-lg px-6 overflow-hidden';
      case 'square_1_1':
        return 'aspect-square rounded-xl object-cover shadow-md w-full max-w-sm mx-auto overflow-hidden';
      case 'story_circle':
        return 'w-24 h-24 rounded-full border-4 border-pink-500 object-cover shadow-lg mx-auto overflow-hidden';
      case 'popup_modal':
        return 'fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4';
      case 'cinematic_21_9':
      default:
        return 'aspect-video md:aspect-[21/9] rounded-xl object-cover shadow-xl w-full overflow-hidden';
    }
  };

  const isModal = banner.display_style === 'popup_modal';

  const Content = (
    <div 
      className={`banner-item relative cursor-pointer transition-transform transform hover:scale-[1.02] ${isModal ? 'bg-white rounded-xl max-w-md mx-auto w-full relative overflow-hidden shadow-2xl' : getStyleClasses()}`}
      data-id={banner.id}
      onClick={onClick}
    >
      {banner.display_style !== 'pill_text' ? (
        <img 
          src={banner.image_url} 
          alt={banner.title} 
          className={`w-full h-full object-cover ${isModal ? 'max-h-64' : ''}`}
        />
      ) : (
        <span className="font-bold text-lg text-center w-full block">{banner.title}</span>
      )}

      {/* Countdown Overlay */}
      {timeLeft && !isModal && (
        <div className="absolute bottom-4 right-4 bg-black bg-opacity-75 text-white px-3 py-1 rounded font-mono text-sm shadow flex items-center gap-2">
          <span className="animate-pulse text-red-400">⏱</span>
          {timeLeft.hours.toString().padStart(2, '0')}:{timeLeft.minutes.toString().padStart(2, '0')}:{timeLeft.seconds.toString().padStart(2, '0')}
        </div>
      )}
      
      {isModal && (
         <div className="p-4 text-center">
            <h3 className="text-xl font-bold mb-2">{banner.title}</h3>
            {timeLeft && (
              <div className="text-red-500 font-bold mt-2">
                 Expires in: {timeLeft.hours}h {timeLeft.minutes}m {timeLeft.seconds}s
              </div>
            )}
            <p className="text-sm text-gray-500 mt-4">(Click anywhere on banner to proceed)</p>
         </div>
      )}
    </div>
  );

  if (isModal) {
    return (
      <div className={getStyleClasses()}>
        {Content}
      </div>
    );
  }

  return Content;
};

export default BannerZone;
