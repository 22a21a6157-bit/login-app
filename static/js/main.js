// ─── Show/Hide Password ───────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.toggle-password').forEach(btn => {
        btn.addEventListener('click', function() {
            const input = this.parentElement.querySelector('.password-field');
            const icon = this.querySelector('i');
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('bi-eye');
                icon.classList.add('bi-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.remove('bi-eye-slash');
                icon.classList.add('bi-eye');
            }
        });
    });

    // Auto-hide toasts after 5 seconds - except a fallback password-reset
    // link, which must never silently disappear before an admin can copy it
    document.querySelectorAll('.toast').forEach(toast => {
        const text = toast.querySelector('.toast-body')?.textContent || '';
        if (text.includes('Reset Link:')) return;
        setTimeout(() => {
            const bsToast = bootstrap.Toast.getOrCreateInstance(toast);
            if (bsToast) bsToast.hide();
        }, 5000);
    });

    initWallpaperRotator();
});

// ─── Dynamic Nature Wallpaper Rotator ─────────────────────
// Curated, freely-licensed (Wikimedia Commons) nature photos, requested at
// a large size for a crisp full-bleed background. If one fails to load
// (network hiccup, renamed file, etc.) it's skipped automatically and the
// rotation just moves on - the page never breaks or shows a blank/broken
// background.
const WALLPAPERS = [
    'https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/Beautiful%20nature%20scenery.jpg&width=2560',
    'https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/1%20moraine%20lake%20pano%202019.jpg&width=2560',
    'https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/Bergpanorama%20(16569535497).jpg&width=2560',
    'https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/Li%20Phi%20falls%20with%20colorful%20sky%20from%20elevated%20zip%20line%20platform%20at%20sunset%20in%20Don%20Khon%20Si%20Phan%20Don%20Laos.jpg&width=2560',
    'https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/Barranco%20Valle%20de%20la%20Fuente%20-%20Fuerteventura.jpg&width=2560',
    'https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/Mondaufgang%20%C3%BCber%20dem%20Meer.jpg&width=2560',
];
const WALLPAPER_INTERVAL_MS = 12000;
const WALLPAPER_FADE_MS = 2500;

function initWallpaperRotator() {
    const layerA = document.getElementById('wallpaper-a');
    const layerB = document.getElementById('wallpaper-b');
    if (!layerA || !layerB) return;

    // Shuffle so different visits (and the two alternating layers) don't
    // always show images in the same order
    const order = [...WALLPAPERS].sort(() => Math.random() - 0.5);
    let pos = 0;
    let activeLayer = layerA;
    let idleLayer = layerB;

    function preload(url) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(url);
            img.onerror = () => reject(new Error('image failed: ' + url));
            img.src = url;
        });
    }

    async function showNext(attemptsLeft) {
        if (attemptsLeft <= 0 || order.length === 0) return; // give up quietly, keep current background
        const url = order[pos % order.length];
        pos++;
        try {
            await preload(url);
            idleLayer.style.backgroundImage = `url("${url}")`;
            idleLayer.classList.add('active');
            activeLayer.classList.remove('active');
            [activeLayer, idleLayer] = [idleLayer, activeLayer];
        } catch (e) {
            // Skip the broken one and try the next candidate immediately
            showNext(attemptsLeft - 1);
        }
    }

    // Set the very first image immediately (no crossfade needed yet)
    showNext(WALLPAPERS.length);
    setInterval(() => showNext(WALLPAPERS.length), WALLPAPER_INTERVAL_MS);
}

// ─── Copy to Clipboard ────────────────────────────────────
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    }).catch(() => {
        // Fallback
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('Copied to clipboard!', 'success');
    });
}

// ─── Toast Notification ───────────────────────────────────
function showToast(message, type = 'info') {
    const container = document.querySelector('.toast-container') || (() => {
        const c = document.createElement('div');
        c.className = 'toast-container position-fixed top-0 end-0 p-3';
        c.style.zIndex = '9999';
        document.body.appendChild(c);
        return c;
    })();

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0 show`;
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 4000);
}
