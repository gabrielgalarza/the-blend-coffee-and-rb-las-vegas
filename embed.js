// Tappable programming cards: toggle .b-is-open, fire Amplitude event
document.querySelectorAll('[data-card]').forEach((card) => {
  card.addEventListener('click', (e) => {
    if (e.target.closest('a')) return;
    if (e.target.closest('.b-rail__nav')) return;
    if (card.hasAttribute('aria-hidden')) return;
    const wasOpen = card.classList.contains('b-is-open');
    card.classList.toggle('b-is-open');

    if (!wasOpen && window.amplitude) {
      const title = card.querySelector('.b-card__title');
      window.amplitude.track('programming_card_expanded', {
        zone: title ? title.textContent.trim() : 'unknown'
      });
    }
  });
});

// Carousel rails: continuous auto-scroll that seamlessly loops + arrow nav.
// We duplicate the track contents in JS so once the user (or auto-scroll)
// reaches the end of the original set, we silently jump scroll position
// back to the start of the duplicate set, giving an infinite-loop feel.
document.querySelectorAll('[data-rail]').forEach((rail) => {
  const viewport = rail.querySelector('.b-rail__viewport');
  const track = rail.querySelector('.b-rail__track');
  const prevBtn = rail.querySelector('.b-rail__nav--prev');
  const nextBtn = rail.querySelector('.b-rail__nav--next');
  if (!viewport || !track) return;

  // Clone all cards once to enable seamless looping. Clones are marked
  // aria-hidden so card-click handlers ignore them.
  const originals = Array.from(track.children);
  let originalsWidth = 0; // computed after layout
  originals.forEach((card) => {
    const clone = card.cloneNode(true);
    clone.setAttribute('aria-hidden', 'true');
    clone.setAttribute('tabindex', '-1');
    track.appendChild(clone);
  });

  const measure = () => {
    // Width of one original set (including the gap that follows it)
    const styles = getComputedStyle(track);
    const gap = parseFloat(styles.columnGap || styles.gap || '16') || 0;
    let w = 0;
    originals.forEach((c) => { w += c.offsetWidth + gap; });
    originalsWidth = w;
  };

  const stepSize = () => {
    const card = track.querySelector('.b-card--rail');
    if (!card) return viewport.clientWidth * 0.8;
    const styles = getComputedStyle(track);
    const gap = parseFloat(styles.columnGap || styles.gap || '16') || 0;
    return card.offsetWidth + gap;
  };

  // If scroll position has passed the originals set, wrap silently to
  // the equivalent position within the originals set (no smooth scroll).
  const normalize = () => {
    if (!originalsWidth) return;
    if (viewport.scrollLeft >= originalsWidth) {
      viewport.scrollLeft = viewport.scrollLeft - originalsWidth;
    } else if (viewport.scrollLeft < 0) {
      viewport.scrollLeft = viewport.scrollLeft + originalsWidth;
    }
  };

  let autoTimer = null;
  let hoverPaused = false;

  const tick = () => {
    if (hoverPaused) return;
    viewport.scrollBy({ left: stepSize(), behavior: 'smooth' });
  };

  const startAuto = () => {
    if (autoTimer) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    autoTimer = setInterval(tick, 4200);
  };

  const stopAuto = () => {
    if (autoTimer) clearInterval(autoTimer);
    autoTimer = null;
  };

  // Wrap after each smooth-scroll completes (~ 600ms is generous)
  let normalizeTimer = null;
  viewport.addEventListener('scroll', () => {
    clearTimeout(normalizeTimer);
    normalizeTimer = setTimeout(normalize, 500);
  }, { passive: true });

  prevBtn?.addEventListener('click', () => {
    viewport.scrollBy({ left: -stepSize(), behavior: 'smooth' });
  });
  nextBtn?.addEventListener('click', () => {
    viewport.scrollBy({ left: stepSize(), behavior: 'smooth' });
  });

  // Pause only while pointer is over the rail; resume on leave.
  // Auto-scroll never stops permanently; it always resumes.
  rail.addEventListener('mouseenter', () => { hoverPaused = true; });
  rail.addEventListener('mouseleave', () => { hoverPaused = false; });

  // Re-measure on resize
  window.addEventListener('resize', () => {
    requestAnimationFrame(measure);
  });

  // Wait for images to settle so widths are accurate
  if (document.readyState === 'complete') {
    measure();
  } else {
    window.addEventListener('load', measure, { once: true });
  }
  // Fallback in case the load event has already fired
  setTimeout(measure, 600);

  setTimeout(startAuto, 1800);
});

// Reveal-on-scroll for non-marquee cards (marquee cards animate via the track)
const io = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
      io.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.b-partner, .b-stat, .b-aud, .b-vendor').forEach((el) => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(14px)';
  el.style.transition = 'opacity .5s ease, transform .5s ease';
  io.observe(el);
});

// Custom Amplitude tracking for high-signal interactions
(function () {
  function track(name, props) {
    if (window.amplitude && typeof window.amplitude.track === 'function') {
      window.amplitude.track(name, props || {});
    }
  }
  function metaTrack(name, props) {
    if (typeof window.fbq === 'function') {
      window.fbq('track', name, props || {});
    }
  }

  // Register CTA clicks. The links go straight to the Sweatpals event page,
  // so this is the only place registration intent is recorded.
  document.querySelectorAll('[data-register]').forEach((el) => {
    el.addEventListener('click', () => {
      const section = el.closest('section');
      track('cta_register_clicked', {
        location: section ? section.id || 'unknown' : 'nav',
        text: el.textContent.trim()
      });
      metaTrack('Lead', { content_name: 'The Blend LA Register' });
    });
  });

  // Nav link clicks (which sections people are jumping to)
  document.querySelectorAll('.b-nav__links a').forEach((el) => {
    el.addEventListener('click', () => {
      track('nav_link_clicked', { section: el.getAttribute('href') });
    });
  });

  // Hero secondary CTA
  const heroSee = document.querySelector('.b-hero__ctas a[href="#included"]');
  if (heroSee) {
    heroSee.addEventListener('click', () => track('hero_see_included_clicked'));
  }

  // Partner email link
  const sponsorEmail = document.querySelector('a[href^="mailto:experienceott"]');
  if (sponsorEmail) {
    sponsorEmail.addEventListener('click', () => track('sponsor_email_clicked'));
  }
})();
