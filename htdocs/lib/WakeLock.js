//
// Screen Wake Lock
//

function WakeLock() {}

WakeLock.lock = null;

WakeLock.request = async function() {
    this.release();
    if (!('wakeLock' in navigator)) {
        console.log('Screen wake lock is unsupported');
    } else {
        try {
            this.lock = await navigator.wakeLock.request('screen');
            console.log('Screen wake lock is now active');
        } catch (err) {
            console.error(`${err.name}: ${err.message}`);
        }
    }

    return this.lock !== null;
};

WakeLock.release = async function() {
    if (this.lock !== null) {
        await this.lock.release();
        this.lock = null;
        console.log('Screen wake lock is now inactive');
    }
};

WakeLock.onVisibility = function() {
  if (this.lock !== null && document.visibilityState === 'visible') {
      this.request();
  }
};

WakeLock.enable = function() {
    // Remove event listener first
    this.disable();
    // Re-acquire the lock if the user switches tabs and returns
    if (this.request()) {
        document.addEventListener('visibilitychange', this.onVisibility);
    }
};

WakeLock.disable = function() {
    document.removeEventListener('visibilitychange', this.onVisibility);
    this.release();
};
