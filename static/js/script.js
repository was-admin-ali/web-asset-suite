// --- AFFILIATE CONFIGURATION ---
const MYFONTS_AFFILIATE_ID = '7707483';

// --- GOOGLE FONTS API CONFIGURATION ---
// IMPORTANT: The API key has been moved to the backend for security.
// This is a placeholder and is no longer used by the script.
const GOOGLE_FONTS_API_KEY = 'YOUR_API_KEY_HERE';

// --- USAGE LIMIT CONFIGURATION (NEW) ---
const MAX_ANON_USES = 3;
const USAGE_COUNT_KEY = 'toolUsageCount';

// --- GLOBAL HELPER FUNCTIONS ---
function loadGoogleFonts(fontsData) {
    const existingLink = document.getElementById('dynamic-google-fonts');
    if (existingLink) {
        existingLink.remove();
    }
    const fontsToLoad = fontsData.filter(font => font.type === 'google').map(font => font.displayName);
    if (fontsToLoad.length === 0) return;
    const fontFamilies = fontsToLoad.map(font => `family=${font.replace(/ /g, '+')}:wght@400;700;800`).join('&');
    const url = `https://fonts.googleapis.com/css2?${fontFamilies}&display=swap`;
    const link = document.createElement('link');
    link.id = 'dynamic-google-fonts';
    link.rel = 'stylesheet';
    link.href = url;
    document.head.appendChild(link);
}

const formatBytes = (bytes, decimals = 2) => {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

// --- CORE CONTRAST CALCULATION LOGIC (SHARED) ---
const hexToRgb = (hex) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? [parseInt(result[1], 16), parseInt(result[2], 16), parseInt(result[3], 16)] : null;
};

const getLuminance = (r, g, b) => {
    const a = [r, g, b].map(v => {
        v /= 255;
        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
};

const getContrastRatio = (hex1, hex2) => {
    const rgb1 = hexToRgb(hex1);
    const rgb2 = hexToRgb(hex2);
    if (!rgb1 || !rgb2) return 1;

    const lum1 = getLuminance(rgb1[0], rgb1[1], rgb1[2]);
    const lum2 = getLuminance(rgb2[0], rgb2[1], rgb2[2]);
    const brightest = Math.max(lum1, lum2);
    const darkest = Math.min(lum1, lum2);

    return (brightest + 0.05) / (darkest + 0.05);
};


// --- USAGE LIMIT LOGIC (NEW) ---
function initUsageLimitModal() {
    const modal = document.getElementById('usage-limit-modal');
    const closeBtn = document.getElementById('usage-limit-close-btn');
    if (!modal || !closeBtn) return;

    const closeModal = () => modal.classList.remove('is-visible');
    closeBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });
}

function showUsageLimitModal() {
    const modal = document.getElementById('usage-limit-modal');
    if (modal) modal.classList.add('is-visible');
}

function checkUsageLimit() {
    const isAuthenticated = document.body.dataset.isAuthenticated === 'true';
    if (isAuthenticated) {
        return true; // Always allow for logged-in users
    }
    const usageCount = parseInt(localStorage.getItem(USAGE_COUNT_KEY) || '0', 10);
    if (usageCount >= MAX_ANON_USES) {
        showUsageLimitModal();
        return false;
    }
    return true;
}

function incrementUsageCount() {
    const isAuthenticated = document.body.dataset.isAuthenticated === 'true';
    if (isAuthenticated) {
        return; // Don't track for logged-in users
    }
    let usageCount = parseInt(localStorage.getItem(USAGE_COUNT_KEY) || '0', 10);
    usageCount++;
    localStorage.setItem(USAGE_COUNT_KEY, usageCount.toString());
    console.log(`Anonymous usage count: ${usageCount}`);
}


// --- INITIALIZATION FUNCTIONS ---
function initThemeSwitcher() {
    const themeToggle = document.getElementById('theme-toggle');
    if (!themeToggle) return;

    const applyTheme = (theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    };

    themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
    });
}

function initMobileNav() {
    const hamburgerBtn = document.getElementById('hamburger-btn');
    const mobileNav = document.getElementById('mobile-nav');
    if (!hamburgerBtn || !mobileNav) return;

    const mobileNavLinks = document.querySelectorAll('.mobile-nav-link, .mobile-nav-btn');
    const toggleMenu = () => {
        hamburgerBtn.classList.toggle('is-active');
        mobileNav.classList.toggle('is-open');
        document.body.classList.toggle('no-scroll'); // This line is correct
        hamburgerBtn.setAttribute('aria-expanded', hamburgerBtn.classList.contains('is-active'));
    };
    hamburgerBtn.addEventListener('click', toggleMenu);
    mobileNavLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (mobileNav.classList.contains('is-open')) {
                toggleMenu();
            }
        });
    });
}

// --- NEW: TOC SCROLLSPY FUNCTION ---
function initTocScrollspy() {
    const tocLinks = document.querySelectorAll('.toc-list a');
    if (tocLinks.length === 0) return;

    // Convert NodeList to Array to use array methods
    const headings = Array.from(document.querySelectorAll('.post-body h2[id], .post-body h3[id]'));
    if (headings.length === 0) return;

    const scrollHandler = () => {
        let currentHeadingId = '';
        const headerOffset = 150; // Adjust this value based on your sticky header height + some margin

        // Find the last heading that is above the activation point (e.g., top of the screen)
        headings.forEach(heading => {
            const headingTop = heading.getBoundingClientRect().top;
            if (headingTop < headerOffset) {
                currentHeadingId = heading.id;
            }
        });

        tocLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href') === `#${currentHeadingId}`) {
                link.classList.add('active');
            }
        });
    };

    window.addEventListener('scroll', scrollHandler, { passive: true });
    scrollHandler(); // Run once on page load to set the initial state
}

// --- MAIN EXTRACTOR TOOL LOGIC ---
function initExtractorTool() {
    const extractForm = document.getElementById('extract-form');
    if (!extractForm) return;

    // Get all DOM elements
    const urlInput = document.getElementById('url-input');
    const extractImagesCheck = document.getElementById('extract-images');
    const extractColorsCheck = document.getElementById('extract-colors');
    const extractFontsCheck = document.getElementById('extract-fonts');
    const loader = document.getElementById('loader');
    const errorMessage = document.getElementById('error-message');
    const resultsContainer = document.getElementById('results-container');
    const imagesSection = document.getElementById('images-section');
    const colorsSection = document.getElementById('colors-section');
    const fontsSection = document.getElementById('fonts-section');
    const imagesGrid = document.getElementById('images-grid');
    const colorsContainer = document.getElementById('colors-container');
    const fontsList = document.getElementById('fonts-list');
    const imageModal = document.getElementById('image-modal');
    const modalImage = document.getElementById('modal-image');
    const modalCloseBtn = document.getElementById('modal-close-btn');

    // --- Result Display Functions ---

    function displayImages(images, pageUrl) {
        imagesGrid.innerHTML = '';
        if (!images || images.length === 0) {
            imagesSection.classList.add('hidden');
            return;
        }
        imagesSection.classList.remove('hidden');
        images.forEach(imageUrl => {
            const item = document.createElement('div');
            item.className = 'image-item';
            const img = document.createElement('img');
            img.src = imageUrl;
            img.alt = 'Extracted Image';
            img.loading = 'lazy';

            const overlay = document.createElement('div');
            overlay.className = 'image-item-overlay';
            
            const downloadUrl = `/download-image?url=${encodeURIComponent(imageUrl)}&page_url=${encodeURIComponent(pageUrl)}`;
            
            overlay.innerHTML = `
                <div class="action-buttons">
                    <button class="action-btn view-btn">
                        <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z" /><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.022 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd" /></svg>
                        View
                    </button>
                    <a href="${downloadUrl}" class="action-btn" download>
                        <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor"><path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" /><path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" /></svg>
                        Download
                    </a>
                </div>`;
            
            item.appendChild(img);
            item.appendChild(overlay);
            imagesGrid.appendChild(item);

            item.querySelector('.view-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                modalImage.src = imageUrl;
                imageModal.classList.add('is-visible');
            });
        });
    }

    function displayColors(colorGroups) {
        colorsContainer.innerHTML = '';
        if (!colorGroups || Object.keys(colorGroups).length === 0) {
            colorsSection.classList.add('hidden');
            return;
        }
        colorsSection.classList.remove('hidden');
        for (const groupName in colorGroups) {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'color-group';
            groupDiv.innerHTML = `<h3 class="color-group-title">${groupName}</h3>`;
            const grid = document.createElement('div');
            grid.className = 'colors-grid';
            colorGroups[groupName].forEach(hex => {
                const box = document.createElement('div');
                box.className = 'color-box';
                box.style.backgroundColor = hex;
                box.innerHTML = `<span>${hex}</span><div class="copy-feedback">Copied!</div>`;
                box.addEventListener('click', () => {
                    navigator.clipboard.writeText(hex);
                    const feedback = box.querySelector('.copy-feedback');
                    feedback.classList.add('visible');
                    setTimeout(() => feedback.classList.remove('visible'), 1500);
                });
                grid.appendChild(box);
            });
            groupDiv.appendChild(grid);
            colorsContainer.appendChild(groupDiv);
        }
    }

    // --- UPDATED FONT DISPLAY FUNCTION ---
    function displayFonts(fonts) {
        fontsList.innerHTML = '';
        if (!fonts || fonts.length === 0) {
            fontsSection.classList.remove('hidden');
            fontsList.innerHTML = '<li class="no-results-message">No specific web fonts identified. The site may be using system default fonts.</li>';
            return;
        }
        fontsSection.classList.remove('hidden');
        
        fonts.forEach(font => {
            const li = document.createElement('li');
            let actionElement = '';

            if (font.type === 'system') {
                // Render info icon for system fonts
                actionElement = `
                    <div class="info-tooltip">
                        <i class="info-icon">i</i>
                        <span class="info-tooltip-text">This is a system font, pre-installed on many operating systems.</span>
                    </div>`;
            } else {
                // Render "Get Font" button for all other fonts
                let link = '#';
                const nameForUrl = font.urlName || font.searchName;
                const fontNameUrl = nameForUrl.replace(/ /g, '+');
                
                switch (font.type) {
                    case 'google':
                        link = `https://fonts.google.com/specimen/${fontNameUrl}`;
                        break;
                    case 'adobe':
                        link = `https://fonts.adobe.com/search?query=${fontNameUrl}`;
                        break;
                    case 'myfonts_direct':
                        link = `https://www.myfonts.com/collections/${nameForUrl.toLowerCase().replace(/ /g, '-')}-font?rfsn=${MYFONTS_AFFILIATE_ID}`;
                        break;
                    case 'myfonts_search':
                        // **FIX IMPLEMENTED HERE**
                        // If a font's source is unknown, a generic Google search is more reliable.
                        link = `https://www.google.com/search?q=${encodeURIComponent(nameForUrl)}+font`;
                        break;
                }
                actionElement = `<a href="${link}" target="_blank" class="get-font-btn">Get Font</a>`;
            }

            li.innerHTML = `
                <div class="font-name-container">
                     <span class="font-name" style="font-family: '${font.displayName}', sans-serif;">${font.displayName}</span>
                </div>
                ${actionElement}`;
            
            fontsList.appendChild(li);
        });

        // Add event listeners for the new tooltips
        const tooltips = fontsList.querySelectorAll('.info-tooltip');
        tooltips.forEach(tooltip => {
            const tooltipText = tooltip.querySelector('.info-tooltip-text');
            tooltip.addEventListener('mouseenter', () => {
                tooltipText.classList.add('visible');
            });
            tooltip.addEventListener('mouseleave', () => {
                tooltipText.classList.remove('visible');
            });
        });
    }

    // --- Form Submission Logic ---
    extractForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const url = urlInput.value.trim();
        if (!url) {
            errorMessage.textContent = 'Please enter a valid URL.';
            errorMessage.classList.remove('hidden');
            return;
        }

        resultsContainer.classList.add('hidden');
        errorMessage.classList.add('hidden');
        loader.classList.remove('hidden');
        
        const payload = {
            url: url,
            'extract_images': extractImagesCheck.checked,
            'extract_colors': extractColorsCheck.checked,
            'extract_fonts': extractFontsCheck.checked,
        };

        try {
            const response = await fetch('/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                if(response.status === 403) showUsageLimitModal();
                throw new Error(data.error || `Server responded with status ${response.status}`);
            }
            
            if(data.fonts) loadGoogleFonts(data.fonts);
            
            displayImages(data.images, url);
            displayColors(data.colors);
            displayFonts(data.fonts);
            
            resultsContainer.classList.remove('hidden');
            resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (error) {
            errorMessage.textContent = `Error: ${error.message}`;
            errorMessage.classList.remove('hidden');
        } finally {
            loader.classList.add('hidden');
        }
    });
    
    // --- Image Modal Logic ---
    if (modalCloseBtn && imageModal) {
        const closeModal = () => imageModal.classList.remove('is-visible');
        modalCloseBtn.addEventListener('click', closeModal);
        imageModal.addEventListener('click', (e) => {
            if (e.target === imageModal) closeModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
        });
    }
}

// --- START: FULLY REVISED AND CORRECTED CONVERTER PAGE LOGIC ---
function initConverterPage() {
    const form = document.getElementById('convert-form');
    if (!form) return;

    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('drop-zone');
    const fileListContainer = document.getElementById('file-list-container');
    const fileList = document.getElementById('file-list');
    const addMoreBtn = document.getElementById('add-more-files-btn');
    const convertBtn = document.getElementById('convert-btn');
    const convertAllSelect = document.getElementById('convert-all-select');
    const convertAllContainer = document.querySelector('.convert-all-container');
    const template = document.getElementById('file-item-template');
    const loader = document.getElementById('convert-loader');
    const errorContainer = document.getElementById('convert-error');
    
    let files = []; // Array to hold File objects

    const showError = (message) => {
        errorContainer.textContent = `Error: ${message}`;
        errorContainer.classList.remove('hidden');
        loader.classList.add('hidden');
    };
    
    const updateUIState = () => {
        const hasFiles = files.length > 0;
        dropZone.classList.toggle('hidden', hasFiles);
        fileListContainer.classList.toggle('hidden', !hasFiles);

        if (convertAllContainer) {
            convertAllContainer.classList.toggle('hidden', files.length <= 1);
        }

        if (hasFiles) {
            updateConvertAllOptions();
        }
    };

    const addFiles = (newFiles) => {
        for (const file of newFiles) {
            const fileId = `${file.name}-${file.lastModified}`;
            if (files.some(f => `${f.name}-${f.lastModified}` === fileId)) continue;

            files.push(file);
            const clone = template.content.cloneNode(true);
            const fileItem = clone.querySelector('.file-item');
            fileItem.dataset.fileId = fileId;
            clone.querySelector('.file-name').textContent = file.name;
            clone.querySelector('.file-size').textContent = formatBytes(file.size);
            
            const dropdown = clone.querySelector('.format-dropdown');

            fetch('/get-supported-formats', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ filename: file.name })
            })
            .then(res => res.json())
            .then(data => {
                if (data.outputs && data.outputs.length > 0) {
                    data.outputs.forEach(format => {
                        const option = new Option(format.toUpperCase(), format);
                        dropdown.add(option);
                    });
                    updateConvertAllOptions();
                } else {
                    dropdown.disabled = true;
                    dropdown.add(new Option('N/A'));
                    fileItem.querySelector('.status-badge').textContent = 'UNSUPPORTED';
                    fileItem.querySelector('.status-badge').classList.add('error');
                }
            });

            clone.querySelector('.remove-file-btn').addEventListener('click', () => {
                files = files.filter(f => `${f.name}-${f.lastModified}` !== fileId);
                document.querySelector(`[data-file-id="${fileId}"]`).remove();
                updateUIState();
            });

            fileList.appendChild(clone);
        }
        updateUIState();
    };

    const updateConvertAllOptions = () => {
        const allDropdowns = [...fileList.querySelectorAll('.format-dropdown:not(:disabled)')];
        if (allDropdowns.length === 0) {
            convertAllSelect.innerHTML = '<option>N/A</option>';
            return;
        }
        
        const commonFormats = allDropdowns.reduce((acc, dropdown) => {
            const formats = [...dropdown.options].map(opt => opt.value);
            return acc.filter(format => formats.includes(format));
        }, [...allDropdowns[0].options].map(opt => opt.value));

        convertAllSelect.innerHTML = '<option value="">Select...</option>';
        commonFormats.forEach(format => {
            convertAllSelect.add(new Option(format.toUpperCase(), format));
        });
    };
    
    convertAllSelect.addEventListener('change', () => {
        if (convertAllSelect.value) {
            fileList.querySelectorAll('.format-dropdown:not(:disabled)').forEach(dd => {
                if ([...dd.options].some(opt => opt.value === convertAllSelect.value)) {
                    dd.value = convertAllSelect.value;
                }
            });
        }
    });

    dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('is-dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('is-dragover'));
    dropZone.addEventListener('drop', (e) => { e.preventDefault(); dropZone.classList.remove('is-dragover'); addFiles(e.dataTransfer.files); });
    dropZone.addEventListener('click', () => fileInput.click());
    addMoreBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
        addFiles(fileInput.files);
        // FIX: Reset input value to allow selecting the same file again
        fileInput.value = null;
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (files.length === 0) return;

        loader.classList.remove('hidden');
        errorContainer.classList.add('hidden');
        convertBtn.disabled = true;
        convertBtn.textContent = 'Converting...';

        const formData = new FormData();
        const fileItems = fileList.querySelectorAll('.file-item');

        fileItems.forEach(item => {
            const fileId = item.dataset.fileId;
            const file = files.find(f => `${f.name}-${f.lastModified}` === fileId);
            const targetFormat = item.querySelector('.format-dropdown').value;
            
            if (file && !item.querySelector('.format-dropdown').disabled) {
                formData.append('files[]', file);
                formData.append('targets[]', targetFormat);
            }
        });

        try {
            const response = await fetch('/convert-files', { method: 'POST', body: formData });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Server responded with status ${response.status}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            
            const disposition = response.headers.get('content-disposition');
            const filenameMatch = disposition && disposition.match(/filename="(.+?)"/);
            a.download = filenameMatch ? filenameMatch[1] : 'converted.zip';
            
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            files = [];
            fileList.innerHTML = '';
            updateUIState();

        } catch (error) {
            showError(error.message);
        } finally {
            loader.classList.add('hidden');
            convertBtn.disabled = false;
            convertBtn.textContent = 'Convert';
        }
    });
}
// --- END: FULLY REVISED AND CORRECTED CONVERTER PAGE LOGIC ---

// --- START: EDITED IMAGE COMPRESSOR PAGE LOGIC ---
function initImageCompressorPage() {
    const compressForm = document.getElementById('compress-form');
    if (!compressForm) return;

    // Get all DOM elements
    const imageInput = document.getElementById('image-input');
    const fileUploadArea = document.getElementById('file-upload-area');
    const fileUploadPrompt = document.getElementById('file-upload-prompt');
    const loader = document.getElementById('compress-loader');
    const errorContainer = document.getElementById('compress-error');
    const resultsContainer = document.getElementById('compress-results');
    const reductionSlider = document.getElementById('reduction-slider');
    const reductionValue = document.getElementById('reduction-value');
    const compressBtn = document.getElementById('compress-btn');
    const multiResultsList = document.getElementById('multi-results-list');
    const totalStatsSummary = document.getElementById('total-stats-summary');
    
    // START: New Modal Elements
    const comparisonModal = document.getElementById('comparison-modal');
    const modalCloseBtn = document.getElementById('comparison-modal-close-btn');
    const modalOriginalPreview = document.getElementById('modal-original-preview');
    const modalCompressedPreview = document.getElementById('modal-compressed-preview');
    // END: New Modal Elements

    let selectedFiles = [];

    const showCompressError = (message) => {
        errorContainer.textContent = `Error: ${message}`;
        errorContainer.classList.remove('hidden');
    };
    
    const updateFileSelection = (files) => {
        selectedFiles = Array.from(files);
        if (selectedFiles.length === 0) {
             fileUploadPrompt.innerHTML = `<svg width="50" height="50" viewBox="0 0 24 24" fill="currentColor"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
                        <p><strong>Click to upload</strong> or drag and drop</p>
                        <span class="file-type-info">PNG or JPG (Max 10MB each)</span>`;
            compressBtn.textContent = 'Compress Image';
        } else if (selectedFiles.length === 1) {
            fileUploadPrompt.innerHTML = `<p>Selected: <strong>${selectedFiles[0].name}</strong></p><span class="file-type-info">Click or drop to change</span>`;
            compressBtn.textContent = 'Compress Image';
        } else {
            fileUploadPrompt.innerHTML = `<p><strong>${selectedFiles.length} files selected</strong></p><span class="file-type-info">Click or drop to change</span>`;
            compressBtn.textContent = `Compress ${selectedFiles.length} Images`;
        }
        resultsContainer.classList.add('hidden');
        errorContainer.classList.add('hidden');
    };

    imageInput.addEventListener('change', () => updateFileSelection(imageInput.files));
    
    fileUploadArea.addEventListener('dragover', (e) => { e.preventDefault(); fileUploadArea.classList.add('is-dragover'); });
    fileUploadArea.addEventListener('dragleave', () => fileUploadArea.classList.remove('is-dragover'));
    fileUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        fileUploadArea.classList.remove('is-dragover');
        updateFileSelection(e.dataTransfer.files);
    });

    if (reductionSlider && reductionValue) {
        const updateSliderAppearance = () => {
            reductionValue.textContent = `${reductionSlider.value}%`;
            const fillPercent = (reductionSlider.value / reductionSlider.max) * 100;
            reductionSlider.style.setProperty('--slider-fill-percent', `${fillPercent}%`);
        };
        reductionSlider.addEventListener('input', updateSliderAppearance);
        updateSliderAppearance();
    }
    
    // START: Modal close logic
    if (comparisonModal && modalCloseBtn) {
        const closeModal = () => comparisonModal.classList.remove('is-visible');
        modalCloseBtn.addEventListener('click', closeModal);
        comparisonModal.addEventListener('click', (e) => {
            if (e.target === comparisonModal) closeModal();
        });
    }
    // END: Modal close logic

    const createResultCard = (file) => {
        const card = document.createElement('div');
        card.className = 'result-card-multi';
        card.id = `result-card-${file.name.replace(/[^a-zA-Z0-9]/g, '-')}`;
        const thumbnailUrl = URL.createObjectURL(file);

        card.innerHTML = `
            <img class="result-thumbnail-multi" src="${thumbnailUrl}" alt="Thumbnail for ${file.name}">
            <div class="result-info-multi">
                <p class="filename-multi">${file.name}</p>
                <p class="size-info-multi">
                    <span class="original-size">${formatBytes(file.size)}</span> &rarr; <span class="compressed-size">...</span>
                </p>
                <p class="status-multi">Waiting...</p>
            </div>
            <div class="result-action-multi">
                <span class="reduction-multi">-0%</span>
                <!-- START: ADDED COMPARE BUTTON -->
                <button class="btn btn-secondary compare-btn hidden">Compare</button>
                <a href="#" class="btn btn-primary download-single-btn hidden">Download</a>
                <!-- END: ADDED COMPARE BUTTON -->
            </div>
        `;
        return card;
    };

    compressForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (selectedFiles.length === 0) {
            showCompressError('Please select one or more images to compress.');
            return;
        }

        loader.classList.remove('hidden');
        resultsContainer.classList.add('hidden');
        errorContainer.classList.add('hidden');
        multiResultsList.innerHTML = '';
        totalStatsSummary.innerHTML = '';
        
        selectedFiles.forEach(file => {
            const card = createResultCard(file);
            multiResultsList.appendChild(card);
        });
        
        resultsContainer.classList.remove('hidden');
        loader.classList.add('hidden');

        let totalOriginalSize = 0, totalCompressedSize = 0, successCount = 0;

        for (const file of selectedFiles) {
            const cardId = `result-card-${file.name.replace(/[^a-zA-Z0-9]/g, '-')}`;
            const card = document.getElementById(cardId);
            const statusEl = card.querySelector('.status-multi');
            statusEl.textContent = 'Compressing...';

            const formData = new FormData();
            formData.append('image', file);
            formData.append('target_reduction', reductionSlider.value);

            try {
                const response = await fetch('/compress-image', { method: 'POST', body: formData });
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    if(response.status === 403) showUsageLimitModal();
                    throw new Error(errorData.error || `Server responded with status ${response.status}`);
                }

                const blob = await response.blob();
                const originalSize = parseInt(response.headers.get('X-Original-Size'), 10);
                const compressedSize = parseInt(response.headers.get('X-Compressed-Size'), 10);

                totalOriginalSize += originalSize;
                totalCompressedSize += compressedSize;
                successCount++;

                card.querySelector('.compressed-size').textContent = formatBytes(compressedSize);
                const reduction = ((originalSize - compressedSize) / originalSize) * 100;
                card.querySelector('.reduction-multi').textContent = `-${Math.max(0, reduction).toFixed(1)}%`;
                
                const originalUrl = URL.createObjectURL(file);
                const compressedUrl = URL.createObjectURL(blob);
                
                const downloadLink = card.querySelector('.download-single-btn');
                downloadLink.href = compressedUrl;
                const disposition = response.headers.get('Content-Disposition');
                const filenameMatch = disposition && disposition.match(/filename="(.+)"/);
                downloadLink.download = filenameMatch ? filenameMatch[1] : `compressed-${file.name}`;
                downloadLink.classList.remove('hidden');
                
                // START: Event Listener for Compare Button
                const compareBtn = card.querySelector('.compare-btn');
                compareBtn.classList.remove('hidden');
                compareBtn.addEventListener('click', () => {
                    modalOriginalPreview.src = originalUrl;
                    modalCompressedPreview.src = compressedUrl;
                    
                    // Reset overlay width before showing
                    const overlay = comparisonModal.querySelector('.img-comp-overlay');
                    if(overlay) overlay.style.width = '50%';

                    comparisonModal.classList.add('is-visible');
                    initComparisons(); // Re-initialize slider on the visible modal
                });
                // END: Event Listener for Compare Button

                statusEl.textContent = 'Success!';
                statusEl.style.color = 'var(--accent-secondary)';

            } catch (error) {
                card.classList.add('is-error');
                statusEl.textContent = error.message.substring(0, 50);
                statusEl.classList.add('error-message');
            }
        }

        if (successCount > 0) {
            const totalReduction = ((totalOriginalSize - totalCompressedSize) / totalOriginalSize) * 100;
            totalStatsSummary.innerHTML = `
                Successfully compressed <strong>${successCount} of ${selectedFiles.length}</strong> images. 
                Total saved: <strong class="total-reduction">${formatBytes(totalOriginalSize - totalCompressedSize)} (${totalReduction.toFixed(1)}%)</strong>
            `;
        } else {
             totalStatsSummary.innerHTML = `<strong>Failed to compress ${selectedFiles.length} images.</strong>`;
        }
    });
}
// --- END: EDITED IMAGE COMPRESSOR PAGE LOGIC ---

// --- START: NEW IMAGE COMPARISON SLIDER LOGIC ---
function initComparisons() {
    const containers = document.getElementsByClassName("img-comp-container");
    // For each container, create a slider and add event listeners
    for (let i = 0; i < containers.length; i++) {
        compareImages(containers[i]);
    }

    function compareImages(container) {
        let clicked = 0;
        const overlay = container.getElementsByClassName("img-comp-overlay")[0];
        
        // Remove existing slider if it exists to prevent duplicates
        const existingSlider = container.getElementsByClassName("img-comp-slider")[0];
        if (existingSlider) {
            existingSlider.remove();
        }

        // Create slider
        const slider = document.createElement("DIV");
        slider.setAttribute("class", "img-comp-slider");
        slider.innerHTML = "<span class='slider-arrow'>&#10231;</span>";
        overlay.parentElement.insertBefore(slider, overlay);

        // Positioning function
        const slideReady = (e) => {
            e.preventDefault();
            clicked = 1;
            window.addEventListener("mousemove", slideMove);
            window.addEventListener("touchmove", slideMove);
        };
        const slideFinish = () => {
            clicked = 0;
        };
        const slideMove = (e) => {
            if (clicked == 0) return false;
            let pos = getCursorPos(e);
            if (pos < 0) pos = 0;
            if (pos > container.offsetWidth) pos = container.offsetWidth;
            slide(pos);
        };
        const getCursorPos = (e) => {
            e = e || window.event;
            const a = container.getBoundingClientRect();
            let x = e.pageX - a.left;
            x = x - window.pageXOffset;
            return x;
        };
        const slide = (x) => {
            overlay.style.width = x + "px";
            slider.style.left = overlay.offsetWidth - (slider.offsetWidth / 2) + "px";
        };

        // Add event listeners
        slider.addEventListener("mousedown", slideReady);
        window.addEventListener("mouseup", slideFinish);
        slider.addEventListener("touchstart", slideReady);
        window.addEventListener("touchend", slideFinish);
        
        // Set initial position
        slide(container.offsetWidth / 2);
    }
}
// --- END: NEW IMAGE COMPARISON SLIDER LOGIC ---

function initContrastChecker() {
    const contrastPage = document.getElementById('contrast-checker-page');
    if (!contrastPage) return;

    const textColorHex = document.getElementById('text-color-hex');
    const textColorSwatch = document.getElementById('text-color-swatch');
    const bgColorHex = document.getElementById('bg-color-hex');
    const bgColorSwatch = document.getElementById('bg-color-swatch');
    const swapBtn = document.getElementById('swap-colors-btn');
    const preview = document.getElementById('contrast-preview');
    const previewButton = document.getElementById('preview-button');
    const ratioCircle = document.getElementById('ratio-circle');
    const ratioDisplay = document.getElementById('contrast-ratio');
    const ratingNormalAA = document.getElementById('rating-normal-aa');
    const ratingLargeAA = document.getElementById('rating-large-aa');

    const passIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd" /></svg>`;
    const failIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd" /></svg>`;

    const updateRating = (element, ratio, threshold) => {
        const statusEl = element.querySelector('.status');
        if (ratio >= threshold) {
            statusEl.innerHTML = `${passIcon} Pass`;
            statusEl.className = 'status pass';
        } else {
            statusEl.innerHTML = `${failIcon} Fail`;
            statusEl.className = 'status fail';
        }
    };
    
    const updateUI = () => {
        const textColor = textColorHex.value;
        const bgColor = bgColorHex.value;
        textColorSwatch.value = textColor;
        bgColorSwatch.value = bgColor;
        preview.style.backgroundColor = bgColor;
        preview.style.color = textColor;
        previewButton.style.backgroundColor = textColor;
        previewButton.style.color = bgColor;
        previewButton.style.borderColor = textColor;
        const ratio = getContrastRatio(textColor, bgColor);
        ratioDisplay.textContent = ratio.toFixed(2);
        ratioCircle.className = 'ratio-circle';
        if (ratio >= 7) ratioCircle.classList.add('pass-aaa');
        else if (ratio >= 4.5) ratioCircle.classList.add('pass-aa');
        else ratioCircle.classList.add('fail');
        updateRating(ratingNormalAA, ratio, 4.5);
        updateRating(ratingLargeAA, ratio, 3);
    };
    
    [textColorHex, textColorSwatch, bgColorHex, bgColorSwatch].forEach(el => {
        el.addEventListener('input', () => {
            if (el.type === 'color') {
                const target = el.id.includes('text') ? textColorHex : bgColorHex;
                target.value = el.value.toUpperCase();
            }
            if (el.type === 'text' && !el.value.startsWith('#')) el.value = '#' + el.value;
            if (el.type === 'text' && el.value.length !== 7) return;
            updateUI();
        });
    });

    swapBtn.addEventListener('click', () => {
        // CORRECTED: Added usage limit check
        if (!checkUsageLimit()) {
            return;
        }
        [textColorHex.value, bgColorHex.value] = [bgColorHex.value, textColorHex.value];
        updateUI();
        incrementUsageCount(); // Increment on successful swap
    });

    updateUI();
}

function initPaletteChecker() {
    const pChecker = document.getElementById('palette-contrast-checker');
    if (!pChecker) return;

    const inputs = document.getElementById('palette-inputs');
    const addBtn = document.getElementById('add-color-btn');
    const checkBtn = document.getElementById('check-palette-btn');
    const resultsContainer = document.getElementById('palette-results-container');
    const resultsGrid = document.getElementById('palette-results-grid');
    const MAX_COLORS = 8;
    const defaultColors = ['#FFFFFF', '#111827', '#4A69FF', '#10B981', '#F59E0B'];

    const createColorInput = (hex) => {
        if (inputs.children.length >= MAX_COLORS) return;
        const row = document.createElement('div');
        row.className = 'palette-color-row';
        row.innerHTML = `
            <div class="color-input-wrapper">
                <input type="color" class="color-input-swatch palette-swatch" value="${hex}">
                <input type="text" class="color-input-hex palette-hex" value="${hex.toUpperCase()}" maxlength="7">
            </div>
            <button class="remove-color-btn" aria-label="Remove color">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" width="20" height="20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd" /></svg>
            </button>`;
        const swatch = row.querySelector('.palette-swatch');
        const hexInput = row.querySelector('.palette-hex');
        swatch.addEventListener('input', () => hexInput.value = swatch.value.toUpperCase());
        hexInput.addEventListener('input', () => { if (hexInput.value.length === 7) swatch.value = hexInput.value; });
        row.querySelector('.remove-color-btn').addEventListener('click', () => {
            row.remove();
            addBtn.classList.toggle('hidden', inputs.children.length >= MAX_COLORS);
        });
        inputs.appendChild(row);
        addBtn.classList.toggle('hidden', inputs.children.length >= MAX_COLORS);
    };

    addBtn.addEventListener('click', () => createColorInput('#000000'));
    
    checkBtn.addEventListener('click', () => {
        // CORRECTED: Added usage limit check
        if (!checkUsageLimit()) {
            return;
        }

        const colors = Array.from(inputs.querySelectorAll('.palette-hex')).map(i => i.value);
        if (colors.length < 2) return;
        resultsGrid.innerHTML = '';
        const gridSize = colors.length + 1;
        resultsGrid.style.gridTemplateColumns = `repeat(${gridSize}, 1fr)`;
        resultsGrid.appendChild(document.createElement('div'));
        colors.forEach(c => {
            const header = document.createElement('div');
            header.className = 'grid-cell grid-header';
            header.innerHTML = `<div class="grid-header-swatch" style="background-color:${c};"></div><span>${c}</span>`;
            resultsGrid.appendChild(header);
        });
        colors.forEach(rowColor => {
            const rowHeader = document.createElement('div');
            rowHeader.className = 'grid-cell grid-header';
            rowHeader.innerHTML = `<div class="grid-header-swatch" style="background-color:${rowColor};"></div><span>${rowColor}</span>`;
            resultsGrid.appendChild(rowHeader);
            colors.forEach(colColor => {
                const cell = document.createElement('div');
                cell.dataset.rowColor = rowColor;
                cell.dataset.colColor = colColor;
                if (rowColor === colColor) {
                    cell.className = 'grid-cell na';
                    cell.textContent = '–';
                } else {
                    const ratio = getContrastRatio(rowColor, colColor);
                    cell.className = 'grid-cell ratio-cell';
                    cell.textContent = ratio.toFixed(2);
                    if (ratio >= 7) cell.classList.add('pass-aaa');
                    else if (ratio >= 4.5) cell.classList.add('pass-aa');
                    else cell.classList.add('fail');
                }
                resultsGrid.appendChild(cell);
            });
        });
        resultsContainer.classList.remove('hidden');
        incrementUsageCount();
    });

    defaultColors.slice(0, 4).forEach(createColorInput);
}

// --- FONT PAIRINGS GENERATOR (MOCKUP FIX) ---
function initFontPairingsGenerator() {
    const generateBtn = document.getElementById('generate-pairing-btn');
    if (!generateBtn) return;

    // Get all DOM elements for the info panel
    const headingNameEl = document.getElementById('heading-font-name');
    const subheadingNameEl = document.getElementById('subheading-font-name');
    const bodyNameEl = document.getElementById('body-font-name');
    const headingLinkEl = document.getElementById('heading-font-link');
    const subheadingLinkEl = document.getElementById('subheading-font-link');
    const bodyLinkEl = document.getElementById('body-font-link');
    const fontLinkTag = document.getElementById('font-pairing-google-font');
    
    // Get all DOM elements for the mockup previews
    const laptopPreview = document.getElementById('font-preview-panel-laptop');
    const phonePreview = document.getElementById('font-preview-panel-phone');

    if (!fontLinkTag) {
        console.error("Fatal Error: The font-pairing-google-font link tag is missing from base.html.");
        return;
    }

    let categorizedFonts = null;

    const fetchAndProcessFonts = async () => {
        try {
            const response = await fetch('/api/google-fonts');
            const data = await response.json();

            if (!response.ok) {
                if(response.status === 403) showUsageLimitModal();
                throw new Error(data.error || `API request failed with status ${response.status}`);
            }
            
            // Filter fonts that have both a regular and a bold weight
            const allPurposeFonts = data.items.filter(f => f.variants.includes('regular') && f.variants.includes('700'));
            
            categorizedFonts = {
                serif: allPurposeFonts.filter(f => f.category === 'serif'),
                'sans-serif': allPurposeFonts.filter(f => f.category === 'sans-serif'),
                display: allPurposeFonts.filter(f => f.category === 'display'),
                handwriting: allPurposeFonts.filter(f => f.category === 'handwriting'),
            };
            
            generateBtn.disabled = false;
            generateBtn.textContent = 'Generate New Pairing';
            generateNewPairing();

        } catch (error) {
            console.error("Failed to fetch or process fonts:", error);
            const errorMessage = error.message.includes('API key is not configured')
                ? "Error: API key not set on server." 
                : "Error: Could not load font data.";
            [laptopPreview, phonePreview].forEach(p => {
                 if(p) p.innerHTML = `<h1>Error</h1><p>${error.message}</p>`;
            });
            generateBtn.textContent = errorMessage;
        }
    };

    const generateNewPairing = () => {
        if (!categorizedFonts) return;

        // Define categories for each role
        const headingCats = ['display', 'serif', 'handwriting', 'sans-serif'];
        const subheadingCats = ['serif', 'sans-serif'];
        const bodyCats = ['sans-serif', 'serif'];

        let headingFont, subheadingFont, bodyFont;
        
        // Loop until all three fonts are distinct
        do {
            const headingCat = headingCats[Math.floor(Math.random() * headingCats.length)];
            const subheadingCat = subheadingCats[Math.floor(Math.random() * subheadingCats.length)];
            const bodyCat = bodyCats[Math.floor(Math.random() * bodyCats.length)];

            const headingList = categorizedFonts[headingCat];
            const subheadingList = categorizedFonts[subheadingCat];
            const bodyList = categorizedFonts[bodyCat];

            headingFont = headingList[Math.floor(Math.random() * headingList.length)].family;
            subheadingFont = subheadingList[Math.floor(Math.random() * subheadingList.length)].family;
            bodyFont = bodyList[Math.floor(Math.random() * bodyList.length)].family;
        } while (headingFont === subheadingFont || subheadingFont === bodyFont || headingFont === bodyFont);

        // Prepare font URLs for Google Fonts API
        const headingUrlPart = headingFont.replace(/ /g, '+') + ':wght@700';
        const subheadingUrlPart = subheadingFont.replace(/ /g, '+') + ':wght@400';
        const bodyUrlPart = bodyFont.replace(/ /g, '+') + ':wght@400';
        fontLinkTag.href = `https://fonts.googleapis.com/css2?family=${headingUrlPart}&family=${subheadingUrlPart}&family=${bodyUrlPart}&display=swap`;

        // Apply fonts to the mockup panels using CSS variables
        [laptopPreview, phonePreview].forEach(panel => {
            if (panel) {
                panel.style.setProperty('--heading-font', `'${headingFont}'`);
                panel.style.setProperty('--subheading-font', `'${subheadingFont}'`);
                panel.style.setProperty('--body-font', `'${bodyFont}'`);
            }
        });

        // Update the info panel with the new font names and links
        headingNameEl.textContent = `${headingFont} Bold`;
        subheadingNameEl.textContent = `${subheadingFont} Regular`;
        bodyNameEl.textContent = `${bodyFont} Regular`;
        
        headingLinkEl.href = `https://fonts.google.com/specimen/${headingFont.replace(/ /g, '+')}`;
        subheadingLinkEl.href = `https://fonts.google.com/specimen/${subheadingFont.replace(/ /g, '+')}`;
        bodyLinkEl.href = `https://fonts.google.com/specimen/${bodyFont.replace(/ /g, '+')}`;
    };

    generateBtn.addEventListener('click', () => {
        if (categorizedFonts) {
            fetchAndProcessFonts();
        } else {
            generateNewPairing();
        }
    });
    
    generateBtn.disabled = true;
    generateBtn.textContent = 'Loading Fonts...';
    fetchAndProcessFonts();
}

function initPasswordToggles() {
    const toggles = document.querySelectorAll('.password-toggle-icon');
    if (toggles.length === 0) return;

    toggles.forEach(toggle => {
        const showIconUrl = toggle.dataset.showIcon;
        const hideIconUrl = toggle.dataset.hideIcon;

        // Preload icons if paths are available to prevent flicker
        if (showIconUrl) new Image().src = showIconUrl;
        if (hideIconUrl) new Image().src = hideIconUrl;

        toggle.addEventListener('click', () => {
            const inputId = toggle.dataset.for;
            const input = document.getElementById(inputId);
            const iconImg = toggle.querySelector('img');

            // Ensure all required elements and data are present
            if (input && iconImg && showIconUrl && hideIconUrl) {
                if (input.type === 'password') {
                    input.type = 'text';
                    iconImg.src = hideIconUrl;
                    iconImg.alt = 'Hide password';
                } else {
                    input.type = 'password';
                    iconImg.src = showIconUrl;
                    iconImg.alt = 'Show password';
                }
            }
        });
    });
}

// --- NEW UNIFIED AUTH FORM VALIDATION ---
function initAuthFormValidation() {
    const form = document.querySelector('.auth-section form');
    if (!form) return;

    // --- Email Validation (runs on both login and register pages) ---
    const emailInput = document.getElementById('email');
    const emailError = document.getElementById('email-error');
    
    const validateEmail = (email) => {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(String(email).toLowerCase());
    };

    if (emailInput && emailError) {
        const checkEmail = () => {
            if (emailInput.value.length > 0 && !validateEmail(emailInput.value)) {
                emailError.classList.remove('hidden');
                emailInput.classList.add('is-invalid');
            } else {
                emailError.classList.add('hidden');
                emailInput.classList.remove('is-invalid');
            }
        };
        emailInput.addEventListener('input', checkEmail);
    }

    // --- Password Validation (only runs on register page) ---
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm_password');
    const lengthError = document.getElementById('password-length-error');
    const matchError = document.getElementById('password-match-error');

    if (passwordInput && confirmPasswordInput && lengthError && matchError) {
        const checkLength = () => {
            if (passwordInput.value.length > 0 && passwordInput.value.length < 8) {
                lengthError.classList.remove('hidden');
                passwordInput.classList.add('is-invalid');
            } else {
                lengthError.classList.add('hidden');
                passwordInput.classList.remove('is-invalid');
            }
        };

        const checkMatch = () => {
            if (confirmPasswordInput.value.length > 0 && passwordInput.value !== confirmPasswordInput.value) {
                matchError.classList.remove('hidden');
                confirmPasswordInput.classList.add('is-invalid');
            } else {
                matchError.classList.add('hidden');
                confirmPasswordInput.classList.remove('is-invalid');
            }
        };

        passwordInput.addEventListener('input', () => {
            checkLength();
            checkMatch(); 
        });
        confirmPasswordInput.addEventListener('input', checkMatch);
    }
    
    // --- Final Check on Form Submission ---
    form.addEventListener('submit', (event) => {
        let isFormValid = true;

        if (emailInput && !validateEmail(emailInput.value)) {
            isFormValid = false;
            emailError.classList.remove('hidden');
            emailInput.classList.add('is-invalid');
        }

        if (passwordInput && confirmPasswordInput) {
            if (passwordInput.value.length < 8) {
                isFormValid = false;
                lengthError.classList.remove('hidden');
                passwordInput.classList.add('is-invalid');
            }
            if (passwordInput.value !== confirmPasswordInput.value) {
                isFormValid = false;
                matchError.classList.remove('hidden');
                confirmPasswordInput.classList.add('is-invalid');
            }
        }

        if (!isFormValid) {
            event.preventDefault(); // Stop submission if any part is invalid
        }
    });
}

// --- NEW FUNCTION for the animated headline ---
function initHeadlineAnimation() {
    const animatedWordEl = document.getElementById('animated-word');
    // Only run this code if the animated word element exists on the page
    if (!animatedWordEl) {
        return;
    }

    const words = ['Images', 'Colors', 'Fonts'];
    let currentIndex = 0;

    setInterval(() => {
        // Apply the fade-out animation
        animatedWordEl.classList.add('word-fade-out');

        // Wait for the fade-out animation to complete (400ms matches the CSS)
        setTimeout(() => {
            // Move to the next word in the array, looping back to the start
            currentIndex = (currentIndex + 1) % words.length;
            animatedWordEl.textContent = words[currentIndex];

            // Swap animation classes to fade the new word in
            animatedWordEl.classList.remove('word-fade-out');
            animatedWordEl.classList.add('word-fade-in');
            
            // Clean up the fade-in class after it finishes so it can be re-applied
            setTimeout(() => {
                animatedWordEl.classList.remove('word-fade-in');
            }, 400);

        }, 400);

    }, 2500); // This sets how long each word stays on screen (2.5 seconds)
}

// --- NEW: Scroll Animation Observer ---
function initScrollAnimations() {
    const sections = document.querySelectorAll('.fade-in-section');
    if (sections.length === 0) return;

    const observer = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1 // Trigger when 10% of the element is visible
    });

    sections.forEach(section => {
        observer.observe(section);
    });
}

function initMobileNavDropdowns() {
    const toggles = document.querySelectorAll('.mobile-nav-toggle');
    toggles.forEach(toggle => {
        toggle.addEventListener('click', () => {
            const submenu = toggle.nextElementSibling;
            toggle.classList.toggle('active');
            submenu.classList.toggle('is-open');
        });
    });
}


// --- MAIN EXECUTION ---
document.addEventListener('DOMContentLoaded', () => {
    if (history.scrollRestoration) history.scrollRestoration = 'manual';
    window.scrollTo(0, 0);
    initThemeSwitcher();
    initMobileNav();
    initExtractorTool();
    initImageCompressorPage();
    initContrastChecker();
    initPaletteChecker();
    initFontPairingsGenerator();
    initPasswordToggles();
    initAuthFormValidation();
    initHeadlineAnimation();
    initTocScrollspy();
    initUsageLimitModal(); // NEW
    initScrollAnimations();
    initMobileNavDropdowns();
    initConverterPage(); // ADDED THIS LINE
});