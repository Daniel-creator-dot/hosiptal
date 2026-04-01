/**
 * Universal Autocomplete Component
 * Works for patients, items, drugs, and any searchable entity
 * Shows popup suggestions as user types
 */

class AutocompleteSearch {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            minChars: 2,
            delay: 300,
            maxResults: 20,
            apiUrl: options.apiUrl || '',
            onSelect: options.onSelect || null,
            displayField: options.displayField || 'name',
            valueField: options.valueField || 'id',
            placeholder: options.placeholder || 'Type to search...',
            // When false, don't show the large "No results found" dropdown
            // (useful for search boxes where the dropdown feels disruptive).
            showNoResults: options.showNoResults !== undefined ? options.showNoResults : true,
            // Optional extra query params appended to API request.
            // Can be: string ("source=all"), object ({source:'all'}), or function returning string/object.
            extraParams: options.extraParams || null,
            ...options
        };
        
        this.results = [];
        this.selectedIndex = -1;
        this.timeout = null;
        this.dropdown = null;
        
        this.init();
    }
    
    init() {
        // Create dropdown container
        this.createDropdown();
        
        // Add event listeners
        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        this.input.addEventListener('focus', () => this.handleFocus());
        this.input.addEventListener('blur', () => {
            // Delay to allow click events on dropdown
            setTimeout(() => this.hideDropdown(), 200);
        });
        
        // Ensure dropdown is positioned relative to wrapper
        this.positionDropdown();
    }
    
    createDropdown() {
        // Prefer an existing dropdown element in the markup (e.g. templates that
        // already provide <div class="autocomplete-dropdown">) to avoid duplicates.
        const inputParent = this.input?.parentElement;
        const existing = inputParent ? inputParent.querySelector('.autocomplete-dropdown') : null;

        if (existing) {
            this.dropdown = existing;
            // Ensure it starts hidden (template CSS may also handle this)
            this.dropdown.style.display = 'none';
        } else {
            this.dropdown = document.createElement('div');
            this.dropdown.className = 'autocomplete-dropdown';
            // Anchor directly under the search control (parent wrapper)
            this.dropdown.style.cssText = `
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.15);
                max-height: 400px;
                overflow-y: auto;
                z-index: 1000;
                display: none;
                width: 100%;
                margin-top: 0;
            `;
            if (inputParent) {
                inputParent.appendChild(this.dropdown);
            }
        }

        if (inputParent) {
            // Critical: dropdown is positioned relative to this wrapper
            inputParent.style.position = inputParent.style.position || 'relative';
        }
    }
    
    positionDropdown() {
        // Keep dropdown anchored to its wrapper. We only need to ensure width
        // stays consistent (some layouts may change on resize).
        window.addEventListener('resize', () => this.updatePosition());
    }
    
    updatePosition() {
        if (!this.dropdown || !this.input) return;

        // The dropdown lives inside a relatively positioned wrapper. Keep it
        // directly under the wrapper (which typically contains the search input
        // and optional button).
        this.dropdown.style.top = '100%';
        this.dropdown.style.left = '0';
        this.dropdown.style.right = '0';
        this.dropdown.style.width = '100%';
    }
    
    handleInput(e) {
        const query = e.target.value.trim();
        
        // Clear previous timeout
        if (this.timeout) {
            clearTimeout(this.timeout);
        }
        
        // Hide dropdown if query is too short
        if (query.length < this.options.minChars) {
            this.hideDropdown();
            return;
        }
        
        // Debounce API call
        this.timeout = setTimeout(() => {
            this.search(query);
        }, this.options.delay);
    }
    
    handleKeydown(e) {
        if (!this.dropdown || this.dropdown.style.display === 'none') {
            return;
        }
        
        const items = this.dropdown.querySelectorAll('.autocomplete-item');
        
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
                this.highlightItem(items);
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
                this.highlightItem(items);
                break;
                
            case 'Enter':
                // Only intercept Enter if user is selecting a suggestion.
                // Otherwise allow the form submit to proceed.
                if (this.selectedIndex >= 0 && items[this.selectedIndex] && !items[this.selectedIndex].classList.contains('autocomplete-no-results')) {
                    e.preventDefault();
                    items[this.selectedIndex].click();
                } else {
                    this.hideDropdown();
                }
                break;
                
            case 'Escape':
                this.hideDropdown();
                break;
        }
    }
    
    handleFocus() {
        const query = this.input.value.trim();
        if (query.length >= this.options.minChars) {
            this.search(query);
        }
    }
    
    async search(query) {
        if (!this.options.apiUrl) {
            console.error('Autocomplete: API URL not provided');
            return;
        }
        
        try {
            // Build optional extra query params
            let extra = this.options.extraParams;
            if (typeof extra === 'function') {
                extra = extra();
            }
            let extraQs = '';
            if (typeof extra === 'string') {
                extraQs = extra.replace(/^\?/, '').trim();
            } else if (extra && typeof extra === 'object') {
                try {
                    extraQs = new URLSearchParams(extra).toString();
                } catch (e) {
                    extraQs = '';
                }
            }

            // Use & when apiUrl already has a query string (e.g. ?encounter_id=... on consultation)
            const baseUrl = this.options.apiUrl;
            const sep = baseUrl.indexOf('?') >= 0 ? '&' : '?';
            const url = `${baseUrl}${sep}q=${encodeURIComponent(query)}${extraQs ? `&${extraQs}` : ''}`;
            const response = await fetch(url, {
                credentials: 'same-origin',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    Accept: 'application/json',
                },
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.results = data[this.options.resultsKey || 'results'] || data.patients || data.items || [];
            this.displayResults();
            
        } catch (error) {
            console.error('Autocomplete search error:', error);
            this.hideDropdown();
        }
    }
    
    displayResults() {
        if (!this.dropdown) return;
        
        if (this.results.length === 0) {
            if (!this.options.showNoResults) {
                this.hideDropdown();
                return;
            }
            this.dropdown.innerHTML = `
                <div class="autocomplete-item autocomplete-no-results" style="padding: 15px; text-align: center; color: #6b7280;">
                    <i class="bi bi-search"></i> No results found
                </div>
            `;
            this.showDropdown();
            return;
        }
        
        const html = this.results.map((item, index) => {
            const displayText = this.getDisplayText(item);
            const highlightText = this.highlightMatch(displayText, this.input.value.trim());
            return `
                <div class="autocomplete-item" data-index="${index}" data-value="${this.getValue(item)}">
                    ${highlightText}
                    ${this.getSubtext(item)}
                </div>
            `;
        }).join('');
        
        this.dropdown.innerHTML = html;
        
        // Add click handlers
        this.dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
            item.addEventListener('click', () => {
                const index = parseInt(item.dataset.index);
                this.selectItem(this.results[index]);
            });
            
            item.addEventListener('mouseenter', () => {
                this.selectedIndex = parseInt(item.dataset.index);
                this.highlightItem(this.dropdown.querySelectorAll('.autocomplete-item'));
            });
        });
        
        this.selectedIndex = -1;
        this.showDropdown();
    }
    
    getDisplayText(item) {
        if (typeof this.options.displayField === 'function') {
            return this.options.displayField(item);
        }
        return item[this.options.displayField] || item.name || item.item_name || item.full_name || JSON.stringify(item);
    }
    
    getValue(item) {
        if (typeof this.options.valueField === 'function') {
            return this.options.valueField(item);
        }
        return item[this.options.valueField] || item.id || item.pk;
    }
    
    getSubtext(item) {
        if (this.options.subtextField) {
            const subtext = typeof this.options.subtextField === 'function' 
                ? this.options.subtextField(item)
                : item[this.options.subtextField];
            
            if (subtext) {
                return `<div class="autocomplete-subtext">${subtext}</div>`;
            }
        }
        return '';
    }
    
    highlightMatch(text, query) {
        if (!query) return text;
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }
    
    highlightItem(items) {
        items.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.classList.add('autocomplete-item-active');
                item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            } else {
                item.classList.remove('autocomplete-item-active');
            }
        });
    }
    
    selectItem(item) {
        if (this.options.onSelect) {
            this.options.onSelect(item, this.input);
        } else {
            // Default behavior: set input value
            this.input.value = this.getDisplayText(item);
        }
        
        this.hideDropdown();
    }
    
    showDropdown() {
        if (!this.dropdown) return;
        this.updatePosition();
        this.dropdown.style.display = 'block';
    }
    
    hideDropdown() {
        if (this.dropdown) {
            this.dropdown.style.display = 'none';
        }
        this.selectedIndex = -1;
    }
}

// CSS Styles (inject into page)
if (!document.getElementById('autocomplete-styles')) {
    const style = document.createElement('style');
    style.id = 'autocomplete-styles';
    style.textContent = `
        /* Force dropdown to stay under the search control (even if an older
           script set inline top/left in pixels). */
        .autocomplete-wrapper {
            position: relative !important;
        }
        .autocomplete-wrapper .autocomplete-dropdown {
            position: absolute !important;
            top: calc(100% + 4px) !important;
            left: 0 !important;
            right: 0 !important;
            width: 100% !important;
        }

        .autocomplete-dropdown {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        
        .autocomplete-item {
            padding: 12px 16px;
            cursor: pointer;
            border-bottom: 1px solid #f3f4f6;
            transition: background-color 0.15s;
            display: flex;
            flex-direction: column;
        }
        
        .autocomplete-item:hover,
        .autocomplete-item-active {
            background-color: #f3f4f6;
        }
        
        .autocomplete-item:last-child {
            border-bottom: none;
        }
        
        .autocomplete-item mark {
            background-color: #fef08a;
            padding: 0 2px;
            font-weight: 600;
        }
        
        .autocomplete-subtext {
            font-size: 0.875rem;
            color: #6b7280;
            margin-top: 4px;
        }
        
        .autocomplete-no-results {
            cursor: default;
        }
        
        .autocomplete-no-results:hover {
            background-color: transparent;
        }
    `;
    document.head.appendChild(style);
}

// Export for use
window.AutocompleteSearch = AutocompleteSearch;
